"""Floorplan 사전 분석 priors — ROI crop + OCR + line detection.

AI 서버의 unet/yolo 추론과 함께 같은 원본 이미지에서 사전 분석 결과를 추출한다.
백엔드는 이 priors 를 받으면 자체 OCR/line 검출을 생략하고, 없으면 fallback.

흐름 (Phase 3):
  1. detect_floorplan_roi(image)        → ROI bbox (source_image 좌표)
  2. crop image to ROI                  → roi_image
  3. extract OCR/line on roi_image      → priors (roi_image 좌표)
  4. translate priors → source_image    → 백엔드 전달 (U-Net 결과와 같은 좌표계)
  5. RoiTransform 도 같이 반환          → 백엔드/프론트가 ROI 정보 활용 가능

U-Net/YOLO 입력은 원본 그대로 유지 — 모델 학습 분포 보호.

출력 dict 는 `packages/contracts/inference.py` 의 `OcrPrior` / `LinePrior` /
`RoiTransform` 와 호환되는 shape (Pydantic 검증을 통과해야 함).

OCR 의존성: easyocr (lru_cache 로 reader 1회 초기화). 미설치/실패 시 빈 리스트 반환.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# Dimension text parser — 백엔드 dimension_matching 과 동일 규칙.
# AI side 에서 parsed_value_m 까지 채워서 보내면 백엔드는 별도 파싱 안 해도 됨.
# ─────────────────────────────────────────────────────────────────────────
_UNIT_PATTERNS: tuple[tuple[re.Pattern, float], ...] = (
    (re.compile(r"(\d+(?:[\.,]\d+)?)\s*mm\b", re.IGNORECASE), 0.001),
    (re.compile(r"(\d+(?:[\.,]\d+)?)\s*cm\b", re.IGNORECASE), 0.01),
    (re.compile(r"(\d+(?:[\.,]\d+)?)\s*m\b", re.IGNORECASE), 1.0),
)
_COMMA_INT_PATTERN = re.compile(r"^\s*(\d{1,3}(?:,\d{3})+)\s*$")
_DECIMAL_PATTERN = re.compile(r"^\s*(\d+\.\d+)\s*$")
_PLAIN_INT_PATTERN = re.compile(r"^\s*(\d{3,5})\s*$")
_PLAIN_INT_MIN_MM = 300
_PLAIN_INT_MAX_MM = 50000


@dataclass(frozen=True)
class _ParsedDim:
    meters: float
    confidence: float


# 흔한 OCR 글자↔숫자 오인식 보정표 (치수 토큰 한정). 백엔드 dimension_matching 과 동일.
_OCR_DIGIT_MAP = str.maketrans({
    "O": "0", "o": "0", "D": "0",
    "I": "1", "l": "1", "|": "1",
    "Z": "2", "z": "2",
    "S": "5", "s": "5",
    "B": "8",
    "g": "9", "q": "9",
    "b": "6",
})


def _normalize_ocr_digits(text: str) -> str | None:
    """숫자 과반 토큰의 글자↔숫자 오인식 보정 ("50O"→"500"). 라벨은 제외."""
    if not text:
        return None
    s = text.strip()
    alnum = [c for c in s if c.isalnum()]
    if not alnum:
        return None
    if sum(c.isdigit() for c in alnum) / len(alnum) < 0.5:
        return None
    normalized = s.translate(_OCR_DIGIT_MAP)
    return normalized if normalized != s else None


def _parse_dimension_meters(text: str) -> _ParsedDim | None:
    parsed = _parse_dimension_meters_raw(text)
    if parsed is not None:
        return parsed
    fixed = _normalize_ocr_digits(text) if isinstance(text, str) else None
    if fixed is not None:
        parsed = _parse_dimension_meters_raw(fixed)
        if parsed is not None:
            return _ParsedDim(meters=parsed.meters, confidence=round(parsed.confidence * 0.8, 3))
    return None


def _parse_dimension_meters_raw(text: str) -> _ParsedDim | None:
    if not isinstance(text, str) or not text:
        return None
    for pat, factor in _UNIT_PATTERNS:
        m = pat.search(text)
        if m:
            try:
                v = float(m.group(1).replace(",", "."))
            except ValueError:
                continue
            meters = v * factor
            if meters > 0:
                return _ParsedDim(meters=meters, confidence=1.0)
    m = _COMMA_INT_PATTERN.match(text)
    if m:
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            return None
        if v > 0:
            return _ParsedDim(meters=v * 0.001, confidence=0.5)
    m = _DECIMAL_PATTERN.match(text)
    if m:
        try:
            v = float(m.group(1))
        except ValueError:
            return None
        if 0 < v <= 30.0:
            return _ParsedDim(meters=v, confidence=0.5)
    m = _PLAIN_INT_PATTERN.match(text)
    if m:
        try:
            v = int(m.group(1))
        except ValueError:
            return None
        if _PLAIN_INT_MIN_MM <= v <= _PLAIN_INT_MAX_MM:
            return _ParsedDim(meters=v / 1000.0, confidence=0.3)
    return None


# ─────────────────────────────────────────────────────────────────────────
# OCR priors — easyocr Reader 캐싱 + bbox/text/kind 분류
# ─────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _get_ocr_reader():
    """프로세스당 1회 reader 초기화 (모델 로드 비용 큼)."""
    try:
        import easyocr
    except ImportError:
        logger.warning("easyocr 미설치 → OCR priors 비활성")
        return None
    try:
        return easyocr.Reader(["ko", "en"], gpu=False, verbose=False)
    except Exception as exc:
        logger.warning("easyocr Reader 초기화 실패: %s", exc)
        return None


def _bbox_orientation(bbox: tuple[float, float, float, float]) -> str:
    x1, y1, x2, y2 = bbox
    w = max(1.0, x2 - x1)
    h = max(1.0, y2 - y1)
    return "horizontal" if w >= h else "vertical"


def _classify_ocr_kind(text: str, parsed: _ParsedDim | None) -> str:
    """OCR 텍스트 → 의미 분류. dimension > scale > room_label > unknown 우선순위."""
    if parsed is not None:
        return "dimension"
    s = (text or "").strip().lower()
    if not s:
        return "unknown"
    # SCALE 1/80, S=1:80 등
    if "scale" in s or "축척" in s or re.search(r"1\s*[:/]\s*\d+", s):
        return "scale"
    # 한국어 방 이름 흔한 케이스 (확장 가능)
    room_words = (
        "방", "안방", "거실", "주방", "욕실", "화장실", "현관",
        "발코니", "베란다", "드레스룸", "다용도실", "서재", "침실",
    )
    if any(w in s for w in room_words):
        return "room_label"
    # 영문 흔한 라벨
    en_room = ("bedroom", "kitchen", "living", "bath", "toilet", "entry", "balcony")
    if any(w in s for w in en_room):
        return "room_label"
    return "unknown"


def extract_ocr_priors(image_bgr: np.ndarray) -> list[dict[str, Any]]:
    """이미지에서 OCR 결과 추출 → OcrPrior 와 호환되는 dict 리스트.

    실패 시 빈 리스트 (호출자가 graceful 처리).
    """
    reader = _get_ocr_reader()
    if reader is None:
        return []

    # easyocr 는 RGB 또는 grayscale 모두 받지만 numpy array 가 안전.
    try:
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        # 전체는 0° 1번, 좌/우 여백 strip 만 회전 OCR (세로 치수). 회전 비용 ↓ + 정확도 ↑.
        raw = _ocr_margin_rotation(reader, rgb)
    except Exception as exc:
        logger.warning("easyocr readtext 실패: %s", exc)
        return []

    priors: list[dict[str, Any]] = []
    for entry in raw:
        if len(entry) < 3:
            continue
        bbox_pts, text, conf = entry[0], entry[1], entry[2]
        try:
            xs = [float(p[0]) for p in bbox_pts]
            ys = [float(p[1]) for p in bbox_pts]
            bbox = (min(xs), min(ys), max(xs), max(ys))
        except (TypeError, IndexError):
            continue
        try:
            confidence = float(conf)
        except (TypeError, ValueError):
            confidence = 0.0

        text_s = str(text)
        parsed = _parse_dimension_meters(text_s)
        kind = _classify_ocr_kind(text_s, parsed)
        priors.append({
            "text": text_s,
            "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]],
            "confidence": confidence,
            "kind": kind,
            "parsed_value_m": (
                round(parsed.meters, 4) if parsed is not None else None
            ),
            "orientation": _bbox_orientation(bbox),
            "coordinate_space": "source_image",
        })
    priors = _dedupe_priors(priors)
    logger.info("OCR priors: %d entries from image", len(priors))
    return priors


# ─────────────────────────────────────────────────────────────────────────
# 여백 strip 회전 OCR — 전체 0° + 좌/우 strip 90°/270° (세로 치수 전용)
# ─────────────────────────────────────────────────────────────────────────
def _readtext_strip(reader, rgb, x0: int, x1: int, rotate_code):
    """좌/우 strip 을 회전해 OCR → (source 좌표 pts, text, conf) 리스트."""
    strip = rgb[:, x0:x1]
    strip_h, strip_w = strip.shape[:2]
    rotated = cv2.rotate(strip, rotate_code)
    res = reader.readtext(rotated, detail=1, paragraph=False)
    out = []
    for entry in res:
        if len(entry) < 3:
            continue
        pts, text, conf = entry[0], entry[1], entry[2]
        try:
            mapped = []
            for p in pts:
                rx, ry = float(p[0]), float(p[1])
                if rotate_code == cv2.ROTATE_90_CLOCKWISE:
                    # 회전이미지(가로=strip_h, 세로=strip_w). src(x,y)=(ry, (strip_h-1)-rx)
                    sx, sy = ry, (strip_h - 1) - rx
                else:  # ROTATE_90_COUNTERCLOCKWISE
                    # src(x,y)=((strip_w-1)-ry, rx) → 단, x 는 strip 내부라 +x0
                    sx, sy = (strip_w - 1) - ry, rx
                mapped.append((sx + x0, sy))
        except (TypeError, IndexError):
            continue
        out.append((mapped, text, conf))
    return out


def _ocr_margin_rotation(reader, rgb, *, strip_ratio: float = 0.16, min_strip_px: int = 40):
    """전체 0° OCR + 좌/우 여백 strip 회전 OCR 결과 합치기.

    세로 치수선은 도면 좌/우 가장자리에만 있으므로, 회전 인식을 전체가 아니라
    가장자리 strip 에만 적용 → rotation_info 전체 적용 대비 비용 ↓, 정확도 ↑.
    반환: easyocr detail=1 과 동일 shape — (bbox4pts(source), text, conf) 리스트.
    """
    results: list = []
    # 1) 전체 이미지 0° (가로 텍스트 대부분)
    for entry in reader.readtext(rgb, detail=1, paragraph=False):
        if len(entry) >= 3:
            results.append((entry[0], entry[1], entry[2]))

    # 2) 좌/우 strip 회전 (세로 텍스트). 양 방향(CW/CCW) 다 시도해 읽는 방향 무관.
    H, W = rgb.shape[:2]
    sw = max(min_strip_px, int(W * strip_ratio))
    sw = min(sw, W)
    strips = [(0, sw)]
    if W - sw > sw:  # 좌/우가 겹치지 않을 때만 우측 strip 추가
        strips.append((W - sw, W))
    for (x0, x1) in strips:
        for code in (cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE):
            try:
                results.extend(_readtext_strip(reader, rgb, x0, x1, code))
            except Exception as exc:
                logger.warning("strip OCR 실패 (x0=%d, code=%s): %s", x0, code, exc)
    return results


def _bbox_iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _dedupe_priors(priors: list[dict[str, Any]], iou_thr: float = 0.4) -> list[dict[str, Any]]:
    """겹치는 OCR 결과 중 confidence 높은 것만 유지 (0°/회전 패스 중복 제거)."""
    ordered = sorted(priors, key=lambda p: float(p.get("confidence", 0.0)), reverse=True)
    kept: list[dict[str, Any]] = []
    for p in ordered:
        pb = p.get("bbox") or []
        if len(pb) != 4:
            continue
        if any(_bbox_iou(pb, k["bbox"]) > iou_thr for k in kept):
            continue
        kept.append(p)
    return kept


# ─────────────────────────────────────────────────────────────────────────
# Line priors — Canny + HoughLinesP, H/V 필터, kind 분류
# ─────────────────────────────────────────────────────────────────────────
def extract_line_priors(
    image_bgr: np.ndarray,
    *,
    canny_low: int = 50,
    canny_high: int = 150,
    hough_threshold: int = 80,
    min_line_length_ratio: float = 0.05,
    max_line_gap: int = 10,
    angle_tolerance_deg: float = 5.0,
) -> list[dict[str, Any]]:
    """Canny + HoughLinesP 로 H/V 선분 후보 추출 → LinePrior dict 리스트.

    `kind="wall_candidate"` 로 채워짐. dimension_line / tick 분류는 Phase 4 에서
    별도 함수가 처리.

    실패 시 빈 리스트.
    """
    if image_bgr is None or image_bgr.size == 0:
        return []
    try:
        gray = (
            cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            if image_bgr.ndim == 3 else image_bgr
        )
    except Exception:
        return []

    h, w = gray.shape
    min_length = max(20, int(min(h, w) * min_line_length_ratio))

    try:
        edges = cv2.Canny(gray, canny_low, canny_high, apertureSize=3)
        raw = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=hough_threshold,
            minLineLength=min_length,
            maxLineGap=max_line_gap,
        )
    except Exception as exc:
        logger.warning("Canny/Hough 실패: %s", exc)
        return []
    if raw is None:
        return []

    segs = raw.reshape(-1, 4)
    if len(segs) == 0:
        return []

    dx = segs[:, 2] - segs[:, 0]
    dy = segs[:, 3] - segs[:, 1]
    angles = np.degrees(np.arctan2(np.abs(dy), np.abs(dx)))  # 0~90
    lengths = np.hypot(dx, dy)
    is_horiz = angles <= angle_tolerance_deg
    is_vert = angles >= (90.0 - angle_tolerance_deg)
    keep = is_horiz | is_vert

    priors: list[dict[str, Any]] = []
    for i, (x1, y1, x2, y2) in enumerate(segs):
        if not keep[i]:
            continue
        orient = "horizontal" if is_horiz[i] else "vertical"
        priors.append({
            "x1": float(x1),
            "y1": float(y1),
            "x2": float(x2),
            "y2": float(y2),
            "length_px": float(lengths[i]),
            "angle_deg": float(angles[i]),
            "orientation": orient,
            "kind": "wall_candidate",
            "confidence": None,
            "source": "hough",
            "coordinate_space": "source_image",
        })
    logger.info(
        "Line priors: %d/%d segments (H/V ±%.1f°, min_len=%d)",
        len(priors), len(segs), angle_tolerance_deg, min_length,
    )
    return priors


# ─────────────────────────────────────────────────────────────────────────
# ROI detection — paper border 제거 + (선택) title block 휴리스틱
# ─────────────────────────────────────────────────────────────────────────
def detect_floorplan_roi(image_bgr: np.ndarray) -> tuple[int, int, int, int]:
    """이미지에서 도면 ROI bbox 검출. (x, y, w, h) source_image 좌표.

    전략 (단순 + 보수적):
      1. Otsu 로 content vs background 이진화
      2. 비배경 픽셀의 global bbox 잡기 (paper border / 흰 여백 자연스럽게 trim)
      3. 작은 margin 추가
      4. 도면이 ROI 의 30% 미만이면 전체 이미지 반환 (잘못된 검출 방지)

    Title block 분리는 추후 별도 휴리스틱(우측 / 하단 박스 검출) 으로 보강 예정.
    실패 시 (전체 이미지, 즉 ROI 비활성) 반환.
    """
    if image_bgr is None or image_bgr.size == 0:
        return (0, 0, 0, 0)
    try:
        gray = (
            cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            if image_bgr.ndim == 3 else image_bgr
        )
    except Exception:
        h, w = image_bgr.shape[:2]
        return (0, 0, w, h)

    H, W = gray.shape[:2]
    # 도면 content 는 어두운 선 → invert binary 로 1=content, 0=배경
    try:
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
        )
    except cv2.error:
        return (0, 0, W, H)

    if binary is None or binary.size == 0:
        return (0, 0, W, H)

    row_has = (binary > 0).any(axis=1)
    col_has = (binary > 0).any(axis=0)
    if not row_has.any() or not col_has.any():
        return (0, 0, W, H)

    rows = np.where(row_has)[0]
    cols = np.where(col_has)[0]
    y1, y2 = int(rows[0]), int(rows[-1])
    x1, x2 = int(cols[0]), int(cols[-1])

    margin = max(5, int(min(W, H) * 0.005))
    x1 = max(0, x1 - margin)
    y1 = max(0, y1 - margin)
    x2 = min(W, x2 + margin + 1)
    y2 = min(H, y2 + margin + 1)

    roi_w, roi_h = x2 - x1, y2 - y1
    # 검출이 의심스러우면 전체로 (예: 노이즈/이진화 실패)
    if roi_w * roi_h < 0.3 * W * H:
        logger.warning(
            "ROI 검출 결과 면적 비율 < 30%% (%dx%d in %dx%d) → 전체 이미지 사용",
            roi_w, roi_h, W, H,
        )
        return (0, 0, W, H)

    logger.info(
        "ROI: source=%dx%d → roi=(%d,%d,%dx%d)",
        W, H, x1, y1, roi_w, roi_h,
    )
    return (x1, y1, roi_w, roi_h)


def _make_roi_transform(
    source_shape: tuple[int, int], roi: tuple[int, int, int, int]
) -> dict[str, Any]:
    """source_image 와 ROI bbox 로 RoiTransform dict 생성 (contract 호환)."""
    H, W = source_shape
    x, y, w, h = roi
    return {
        "source_width": int(W),
        "source_height": int(H),
        "roi_x": float(x),
        "roi_y": float(y),
        "roi_width": float(w),
        "roi_height": float(h),
        "output_width": int(w),    # resize 없음 → output = ROI 그대로
        "output_height": int(h),
        "scale_x": 1.0,
        "scale_y": 1.0,
        "coordinate_space": "roi_image",
    }


def _translate_ocr_prior_to_source(
    prior: dict[str, Any], offset_x: int, offset_y: int
) -> dict[str, Any]:
    """ROI 좌표계 OcrPrior → source_image 좌표계로 bbox 시프트."""
    bbox = prior.get("bbox") or []
    if len(bbox) == 4:
        prior = dict(prior)  # 얕은 복사
        prior["bbox"] = [
            float(bbox[0]) + offset_x,
            float(bbox[1]) + offset_y,
            float(bbox[2]) + offset_x,
            float(bbox[3]) + offset_y,
        ]
    prior["coordinate_space"] = "source_image"
    return prior


def _translate_line_prior_to_source(
    prior: dict[str, Any], offset_x: int, offset_y: int
) -> dict[str, Any]:
    """ROI 좌표계 LinePrior → source_image 좌표계로 좌표 시프트."""
    out = dict(prior)
    if "x1" in out:
        out["x1"] = float(out["x1"]) + offset_x
        out["y1"] = float(out["y1"]) + offset_y
        out["x2"] = float(out["x2"]) + offset_x
        out["y2"] = float(out["y2"]) + offset_y
    out["coordinate_space"] = "source_image"
    return out


def _classify_dimension_lines(
    ocr_priors: list[dict[str, Any]],
    line_priors: list[dict[str, Any]],
    *,
    image_shape: tuple[int, int],
) -> list[dict[str, Any]]:
    """OCR 치수 텍스트에 평행하게 붙은 선분을 dimension_line 으로 재분류.

    치수선(dimension line)은 정의상 치수 숫자를 동반한다 → 같은 방향(H/V)의
    dimension 텍스트가 선분에 충분히 가까우면(수직거리 작고 선분 span 안) 치수선으로 본다.
    재분류된 선분은 백엔드 line_mask 에서 wall_candidate 필터에 걸려 벽 점수에서 제외된다.

    `ocr_priors` 와 `line_priors` 는 **같은 좌표계** 여야 한다 (둘 다 source_image 권장).
    """
    dims = [
        p for p in ocr_priors
        if p.get("kind") == "dimension" and len(p.get("bbox") or []) == 4
    ]
    if not dims or not line_priors:
        return line_priors

    H, W = image_shape
    perp_tol = max(12.0, 0.02 * min(H, W))     # 선분 ↔ 텍스트 수직 거리 허용
    span_margin = max(20.0, 0.03 * max(H, W))  # 선분 span 바깥 텍스트 허용

    dim_centers: list[tuple[float, float, str | None]] = []
    for d in dims:
        bx1, by1, bx2, by2 = (float(v) for v in d["bbox"])
        dim_centers.append(((bx1 + bx2) / 2.0, (by1 + by2) / 2.0, d.get("orientation")))

    out: list[dict[str, Any]] = []
    reclassified = 0
    for p in line_priors:
        if p.get("kind") != "wall_candidate" or not all(
            k in p for k in ("x1", "y1", "x2", "y2")
        ):
            out.append(p)
            continue
        orient = p.get("orientation")
        lx1, ly1, lx2, ly2 = float(p["x1"]), float(p["y1"]), float(p["x2"]), float(p["y2"])
        is_dim = False
        for cx, cy, dorient in dim_centers:
            if dorient != orient:
                continue
            if orient == "horizontal":
                line_y = (ly1 + ly2) / 2.0
                lo, hi = min(lx1, lx2), max(lx1, lx2)
                if abs(cy - line_y) <= perp_tol and (lo - span_margin) <= cx <= (hi + span_margin):
                    is_dim = True
                    break
            else:  # vertical
                line_x = (lx1 + lx2) / 2.0
                lo, hi = min(ly1, ly2), max(ly1, ly2)
                if abs(cx - line_x) <= perp_tol and (lo - span_margin) <= cy <= (hi + span_margin):
                    is_dim = True
                    break
        if is_dim:
            p = dict(p)
            p["kind"] = "dimension_line"
            reclassified += 1
        out.append(p)

    if reclassified:
        logger.info(
            "Dimension lines: %d/%d 선분을 치수선으로 재분류 (벽 후보 제외)",
            reclassified, len(line_priors),
        )
    return out


def extract_floorplan_priors(image_bgr: np.ndarray) -> dict[str, Any]:
    """ROI crop → OCR + line priors → source_image 좌표로 복원해 반환.

    반환 dict shape:
      {
        "ocrPriors":   [OcrPrior dict, ...],   # source_image 좌표
        "linePriors":  [LinePrior dict, ...],  # source_image 좌표
        "roiTransform": RoiTransform dict      # 또는 None (ROI 비활성/검출 실패)
      }
    """
    if image_bgr is None or image_bgr.size == 0:
        return {"ocrPriors": [], "linePriors": [], "roiTransform": None}

    H, W = image_bgr.shape[:2]
    roi = detect_floorplan_roi(image_bgr)
    x, y, w, h = roi
    roi_used = not (x == 0 and y == 0 and w == W and h == H)

    if roi_used and w > 0 and h > 0:
        roi_image = image_bgr[y:y + h, x:x + w]
        ocr_roi = extract_ocr_priors(roi_image)
        line_roi = extract_line_priors(roi_image)
        ocr_priors = [_translate_ocr_prior_to_source(p, x, y) for p in ocr_roi]
        line_priors = [_translate_line_prior_to_source(p, x, y) for p in line_roi]
        roi_transform = _make_roi_transform((H, W), roi)
    else:
        # ROI 가 전체 이미지와 같으면 굳이 crop 안 함 (원본 그대로 사용).
        ocr_priors = extract_ocr_priors(image_bgr)
        line_priors = extract_line_priors(image_bgr)
        # RoiTransform 은 ROI 정보 제공 차원에서 "ROI = 전체 이미지" 로 채워줌.
        roi_transform = _make_roi_transform((H, W), (0, 0, W, H))

    # 치수선 재분류 — ocr/line 모두 source_image 좌표인 시점에서 수행.
    line_priors = _classify_dimension_lines(
        ocr_priors, line_priors, image_shape=(H, W)
    )

    return {
        "ocrPriors": ocr_priors,
        "linePriors": line_priors,
        "roiTransform": roi_transform,
    }
