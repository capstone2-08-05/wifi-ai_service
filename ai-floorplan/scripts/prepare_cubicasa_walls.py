from __future__ import annotations

import argparse
import random
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw


WALL_KEYWORDS = {
    "wall",
    "walls",
    "interior wall",
    "exterior wall",
    "railing wall",
}

IMAGE_EXTS = {".png", ".jpg", ".jpeg"}

NUMBER_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")
PATH_TOKEN_RE = re.compile(
    r"[MmLlHhVvZzCcSsQqTtAa]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?"
)

EXCLUDE_KEYWORDS = {
    "door",
    "doors",
    "window",
    "windows",
    "opening",
    "openings",
    "entrance",
    "swing",
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw_root", type=str, required=True)
    parser.add_argument("--out_root", type=str, required=True)
    parser.add_argument("--val_ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def local_tag(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def parse_float(text: str | None, default: float = 0.0) -> float:
    if text is None:
        return default
    m = NUMBER_RE.search(text)
    return float(m.group()) if m else default


def parse_style(style_text: str | None) -> dict[str, str]:
    if not style_text:
        return {}
    result = {}
    for item in style_text.split(";"):
        if ":" not in item:
            continue
        k, v = item.split(":", 1)
        result[k.strip().lower()] = v.strip()
    return result


def element_text_blob(elem: ET.Element) -> str:
    parts = [local_tag(elem.tag)]
    for k, v in elem.attrib.items():
        parts.append(f"{k}={v}")
    if elem.text:
        parts.append(elem.text)
    return " ".join(parts).lower()


def is_wall_like(elem: ET.Element, inherited_match: bool = False) -> bool:
    blob = element_text_blob(elem)
    matched = any(keyword in blob for keyword in WALL_KEYWORDS)
    return inherited_match or matched

def is_excluded_like(elem: ET.Element, inherited_match: bool = False) -> bool:
    blob = element_text_blob(elem)
    matched = any(keyword in blob for keyword in EXCLUDE_KEYWORDS)
    return inherited_match or matched

def find_svg_dirs(raw_root: Path) -> list[Path]:
    return sorted([p.parent for p in raw_root.rglob("model.svg")])


def choose_image_file(sample_dir: Path) -> Path | None:
    candidates = [p for p in sample_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS]
    if not candidates:
        return None

    scaled = [p for p in candidates if "scaled" in p.stem.lower()]
    if scaled:
        return sorted(scaled)[0]

    return sorted(candidates)[0]


def parse_viewbox(
    root: ET.Element, out_w: int, out_h: int
) -> tuple[float, float, float, float]:
    vb = root.attrib.get("viewBox")
    if vb:
        nums = [float(x) for x in NUMBER_RE.findall(vb)]
        if len(nums) == 4 and nums[2] > 0 and nums[3] > 0:
            return nums[0], nums[1], nums[2], nums[3]
    return 0.0, 0.0, float(out_w), float(out_h)


def make_scaler(root: ET.Element, out_w: int, out_h: int):
    min_x, min_y, vb_w, vb_h = parse_viewbox(root, out_w, out_h)

    def scale_point(x: float, y: float) -> tuple[float, float]:
        px = (x - min_x) * out_w / vb_w
        py = (y - min_y) * out_h / vb_h
        return px, py

    def scale_length(v: float) -> int:
        scale = (out_w / vb_w + out_h / vb_h) / 2.0
        return max(1, int(round(v * scale)))

    return scale_point, scale_length


def parse_points_attr(points_text: str | None) -> list[tuple[float, float]]:
    if not points_text:
        return []
    nums = [float(x) for x in NUMBER_RE.findall(points_text)]
    points = []
    for i in range(0, len(nums) - 1, 2):
        points.append((nums[i], nums[i + 1]))
    return points


def parse_path_to_subpaths(d: str | None) -> list[tuple[list[tuple[float, float]], bool]]:
    if not d:
        return []

    tokens = PATH_TOKEN_RE.findall(d)
    i = 0
    cmd = None

    current = (0.0, 0.0)
    start = None
    subpaths: list[tuple[list[tuple[float, float]], bool]] = []
    points: list[tuple[float, float]] = []
    closed = False

    def flush():
        nonlocal points, closed
        if points:
            subpaths.append((points[:], closed))
        points = []
        closed = False

    def next_num() -> float:
        nonlocal i
        v = float(tokens[i])
        i += 1
        return v

    while i < len(tokens):
        if re.fullmatch(r"[A-Za-z]", tokens[i]):
            cmd = tokens[i]
            i += 1
        elif cmd is None:
            raise ValueError("Invalid path data: command expected.")

        if cmd in ("M", "m"):
            flush()
            x = next_num()
            y = next_num()
            if cmd == "m":
                current = (current[0] + x, current[1] + y)
            else:
                current = (x, y)
            start = current
            points = [current]

            while i < len(tokens) and not re.fullmatch(r"[A-Za-z]", tokens[i]):
                x = next_num()
                y = next_num()
                if cmd == "m":
                    current = (current[0] + x, current[1] + y)
                else:
                    current = (x, y)
                points.append(current)

        elif cmd in ("L", "l"):
            while i < len(tokens) and not re.fullmatch(r"[A-Za-z]", tokens[i]):
                x = next_num()
                y = next_num()
                if cmd == "l":
                    current = (current[0] + x, current[1] + y)
                else:
                    current = (x, y)
                points.append(current)

        elif cmd in ("H", "h"):
            while i < len(tokens) and not re.fullmatch(r"[A-Za-z]", tokens[i]):
                x = next_num()
                if cmd == "h":
                    current = (current[0] + x, current[1])
                else:
                    current = (x, current[1])
                points.append(current)

        elif cmd in ("V", "v"):
            while i < len(tokens) and not re.fullmatch(r"[A-Za-z]", tokens[i]):
                y = next_num()
                if cmd == "v":
                    current = (current[0], current[1] + y)
                else:
                    current = (current[0], y)
                points.append(current)

        elif cmd in ("C", "c"):
            while i < len(tokens) and not re.fullmatch(r"[A-Za-z]", tokens[i]):
                nums = [next_num() for _ in range(6)]
                x, y = nums[-2], nums[-1]
                if cmd == "c":
                    current = (current[0] + x, current[1] + y)
                else:
                    current = (x, y)
                points.append(current)

        elif cmd in ("S", "s", "Q", "q"):
            while i < len(tokens) and not re.fullmatch(r"[A-Za-z]", tokens[i]):
                nums = [next_num() for _ in range(4)]
                x, y = nums[-2], nums[-1]
                if cmd.islower():
                    current = (current[0] + x, current[1] + y)
                else:
                    current = (x, y)
                points.append(current)

        elif cmd in ("T", "t"):
            while i < len(tokens) and not re.fullmatch(r"[A-Za-z]", tokens[i]):
                x = next_num()
                y = next_num()
                if cmd == "t":
                    current = (current[0] + x, current[1] + y)
                else:
                    current = (x, y)
                points.append(current)

        elif cmd in ("A", "a"):
            while i < len(tokens) and not re.fullmatch(r"[A-Za-z]", tokens[i]):
                nums = [next_num() for _ in range(7)]
                x, y = nums[-2], nums[-1]
                if cmd == "a":
                    current = (current[0] + x, current[1] + y)
                else:
                    current = (x, y)
                points.append(current)

        elif cmd in ("Z", "z"):
            closed = True
            if start is not None and points and points[-1] != start:
                points.append(start)
            flush()
            start = None

    flush()
    return subpaths


def draw_polygon(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]]) -> bool:
    if len(points) < 3:
        return False
    draw.polygon(points, fill=255, outline=255)
    return True


def draw_polyline(
    draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], width: int
) -> bool:
    if len(points) < 2:
        return False
    draw.line(points, fill=255, width=width)
    return True


def draw_element(
    draw: ImageDraw.ImageDraw,
    elem: ET.Element,
    scale_point,
    scale_length,
) -> bool:
    tag = local_tag(elem.tag)
    style = parse_style(elem.attrib.get("style"))
    stroke_width = parse_float(
        elem.attrib.get("stroke-width"),
        default=parse_float(style.get("stroke-width"), 2.0),
    )
    width_px = scale_length(stroke_width)

    if tag == "polygon":
        pts = [scale_point(x, y) for x, y in parse_points_attr(elem.attrib.get("points"))]
        return draw_polygon(draw, pts)

    if tag == "polyline":
        pts = [scale_point(x, y) for x, y in parse_points_attr(elem.attrib.get("points"))]
        return draw_polyline(draw, pts, width_px)

    if tag == "rect":
        x = parse_float(elem.attrib.get("x"))
        y = parse_float(elem.attrib.get("y"))
        w = parse_float(elem.attrib.get("width"))
        h = parse_float(elem.attrib.get("height"))
        pts = [
            scale_point(x, y),
            scale_point(x + w, y),
            scale_point(x + w, y + h),
            scale_point(x, y + h),
        ]
        return draw_polygon(draw, pts)

    if tag == "line":
        x1 = parse_float(elem.attrib.get("x1"))
        y1 = parse_float(elem.attrib.get("y1"))
        x2 = parse_float(elem.attrib.get("x2"))
        y2 = parse_float(elem.attrib.get("y2"))
        return draw_polyline(
            draw,
            [scale_point(x1, y1), scale_point(x2, y2)],
            width_px,
        )

    if tag == "circle":
        cx = parse_float(elem.attrib.get("cx"))
        cy = parse_float(elem.attrib.get("cy"))
        r = parse_float(elem.attrib.get("r"))
        x1, y1 = scale_point(cx - r, cy - r)
        x2, y2 = scale_point(cx + r, cy + r)
        draw.ellipse([x1, y1, x2, y2], fill=255, outline=255)
        return True

    if tag == "ellipse":
        cx = parse_float(elem.attrib.get("cx"))
        cy = parse_float(elem.attrib.get("cy"))
        rx = parse_float(elem.attrib.get("rx"))
        ry = parse_float(elem.attrib.get("ry"))
        x1, y1 = scale_point(cx - rx, cy - ry)
        x2, y2 = scale_point(cx + rx, cy + ry)
        draw.ellipse([x1, y1, x2, y2], fill=255, outline=255)
        return True

    if tag == "path":
        subpaths = parse_path_to_subpaths(elem.attrib.get("d"))
        drew_any = False
        for pts, closed in subpaths:
            scaled = [scale_point(x, y) for x, y in pts]
            if closed:
                drew_any = draw_polygon(draw, scaled) or drew_any
            else:
                drew_any = draw_polyline(draw, scaled, width_px) or drew_any
        return drew_any

    return False

def render_wall_mask(svg_path: Path, out_mask_path: Path, width: int, height: int) -> int:
    tree = ET.parse(svg_path)
    root = tree.getroot()

    wall_mask = Image.new("L", (width, height), 0)
    exclude_mask = Image.new("L", (width, height), 0)

    wall_draw = ImageDraw.Draw(wall_mask)
    exclude_draw = ImageDraw.Draw(exclude_mask)

    scale_point, scale_length = make_scaler(root, width, height)
    drawn_count = 0

    def visit_wall(elem: ET.Element, inherited_match: bool = False):
        nonlocal drawn_count
        matched = is_wall_like(elem, inherited_match)
        tag = local_tag(elem.tag)

        if matched and tag in {
            "path",
            "polygon",
            "polyline",
            "rect",
            "line",
            "circle",
            "ellipse",
        }:
            if draw_element(wall_draw, elem, scale_point, scale_length):
                drawn_count += 1

        for child in list(elem):
            visit_wall(child, matched)

    def visit_exclude(elem: ET.Element, inherited_match: bool = False):
        matched = is_excluded_like(elem, inherited_match)
        tag = local_tag(elem.tag)

        if matched and tag in {
            "path",
            "polygon",
            "polyline",
            "rect",
            "line",
            "circle",
            "ellipse",
        }:
            draw_element(exclude_draw, elem, scale_point, scale_length)

        for child in list(elem):
            visit_exclude(child, matched)

    visit_wall(root, False)
    visit_exclude(root, False)

    wall_mask = wall_mask.point(lambda p: 255 if p > 10 else 0)
    exclude_mask = exclude_mask.point(lambda p: 255 if p > 10 else 0)

    wall_img = wall_mask.load()
    exclude_img = exclude_mask.load()

    for y in range(height):
        for x in range(width):
            if exclude_img[x, y] > 0:
                wall_img[x, y] = 0

    out_mask_path.parent.mkdir(parents=True, exist_ok=True)
    wall_mask.save(out_mask_path)

    return drawn_count


def build_pairs(raw_root: Path) -> list[tuple[Path, Path]]:
    pairs = []
    for sample_dir in find_svg_dirs(raw_root):
        svg_path = sample_dir / "model.svg"
        image_path = choose_image_file(sample_dir)
        if image_path is not None:
            pairs.append((image_path, svg_path))
    return pairs


def copy_pair_to_split(
    image_path: Path,
    svg_path: Path,
    out_root: Path,
    split: str,
    idx: int,
) -> None:
    image_out_dir = out_root / "images" / split
    mask_out_dir = out_root / "masks" / split
    image_out_dir.mkdir(parents=True, exist_ok=True)
    mask_out_dir.mkdir(parents=True, exist_ok=True)

    stem = f"{idx:06d}"
    out_image_path = image_out_dir / f"{stem}{image_path.suffix.lower()}"
    out_mask_path = mask_out_dir / f"{stem}.png"

    shutil.copy2(image_path, out_image_path)

    with Image.open(image_path) as img:
        width, height = img.size

    drawn_count = render_wall_mask(svg_path, out_mask_path, width=width, height=height)

    if drawn_count == 0:
        print(f"[WARN] no wall elements drawn: {svg_path}")


def main() -> None:
    args = parse_args()
    raw_root = Path(args.raw_root)
    out_root = Path(args.out_root)

    pairs = build_pairs(raw_root)
    if not pairs:
        raise ValueError("No (image, model.svg) pairs found. Check raw_root path.")

    random.seed(args.seed)
    random.shuffle(pairs)

    n_total = len(pairs)
    n_val = int(n_total * args.val_ratio)

    val_pairs = pairs[:n_val]
    train_pairs = pairs[n_val:]

    print(f"Found {n_total} pairs | train={len(train_pairs)} | val={len(val_pairs)}")

    for idx, (image_path, svg_path) in enumerate(train_pairs):
        copy_pair_to_split(image_path, svg_path, out_root, "train", idx)

    for idx, (image_path, svg_path) in enumerate(val_pairs):
        copy_pair_to_split(image_path, svg_path, out_root, "val", idx)

    print("Done.")


if __name__ == "__main__":
    main()