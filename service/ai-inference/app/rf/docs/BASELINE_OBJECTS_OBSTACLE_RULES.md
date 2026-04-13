# Baseline: objects 장애물 규칙 (초안)

구현: `object_obstacle_rules.py`, `BaselineRfSimulator._compute_obstacle_loss_on_los`.

## 1. 의도 (교수님 피드백 대응)

- 복잡한 **3D furniture model** 없음.
- **2D obstacle zone**: 바닥면 투영(축정렬 bbox 또는 `points` 의 AABB).
- **추가 감쇠**: AP–수신 **직선(LOS)** 이 그 영역과 **겹치면** 링크 예산에서 dB 감산.
- “가구 배치에 따라 품질이 달라진다”: 같은 격자점이라도 AP–해당 점 연직선이 책상·수납장 영역을 **지나가면** RSSI가 더 낮아질 수 있다.

## 2. 기하

- 각 object dict에 대해 `object_bbox_m()` 이 사각형 `(min_x, max_x, min_y, max_y)` 를 구한다.
  - `footprint_m` / `bbox_m` 우선, 없으면 `points` 의 min/max.
- 선분 `(AP_x, AP_y)`–`(Rx_x, Rx_y)` 가 이 사각형과 **교차**하거나, 끝점이 사각형 **내부**에 있으면 “LOS가 장애물과 겹친다”고 본다 (`segment_intersects_aabb`).

## 3. 손실 크기 [dB]

`resolve_object_loss_db(obj)`:

1. `attenuation_db` 가 양수로 주어지면 그 값.
2. 아니면 `obstacle_class` 또는 `type` → `DEFAULT_OBSTACLE_CLASS_DB`.
3. 아니면 `material`(가구) → `DEFAULT_OBSTACLE_MATERIAL_DB`.
4. 없으면 `unknown` 클래스 기본값.

여러 object와 겹치면 **손실을 합산**하고, 전체 **합산 상한**은 `baseline_rf_simulator._MAX_OBJECT_OBSTACLE_DB` (현재 25 dB).

## 4. 한계 (preview)

- 주파수·극화·다경로 없음; **가구 내부 다층 구조** 없음.
- `points` 가 볼록/오목 다각형이어도 교차 판정은 **AABB 근사**만 사용 (향후 다각형–선분 정밀 교차 가능).
- `height` 는 Baseline에서 **미사용** (Sionna·후속 3D에서 소비).

## 5. Sionna와의 관계

- Baseline: 위 2D 규칙 + 고정 dB.
- Sionna: 동일 `objects[]` 를 씬 플랜에 전달할 수 있으나, **물리 모델은 엔진**; 의미만 “같은 배치가 더 정밀 엔진에서도 반영될 수 있게” 맞춘다.
