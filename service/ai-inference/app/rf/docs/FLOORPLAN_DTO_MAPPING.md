# Floorplan DTO → RF canonical 매핑

혜승 백엔드 `backend/app/schemas/floorplan.py`(`SceneSchema`, `Wall`, `Opening`, `Room`)와 RF 측 `rf_models.Scene` 사이의 필드 대응이다. 변환 구현은 `adapter_baseline_dto.scene_schema_to_baseline_rf_scene_dict` 및 `scene_to_rf_adapter.scene_schema_to_rf_scene_dict`를 참고하면 된다.

## 좌표·단위

| DTO | RF |
|-----|-----|
| `units` (리터럴 `"m"`) | `units`: `"m"` |
| 벽·개구·방의 x, y | 동일 (floor-local **meter**). z는 DTO에 없고, baseline은 2D 평면 기준. |

`units != "m"` 이면 RF로 넘기지 않는다 (`ValueError`).

## 루트

| DTO 필드 | RF 필드 | 비고 |
|----------|---------|------|
| `scene_version` | `scene_version_id` | 문자열 그대로 strip |
| `sourceType` | `sourceType` | |
| `scale_ratio` | (미전달) | RF canonical 루트에는 없음 |
| `topology` | (미전달) | 필요 시 별도 저장/확장 |
| `walls` / `openings` / `rooms` / `objects` | 동명 배열 (내용 변환 아래) | |

선택 인자 `floor_id`를 어댑터에 넘기면 RF `floor_id`에 들어간다.

## 벽 `Wall`

| DTO | RF `Wall` dict |
|-----|----------------|
| `id` | `id` |
| `x1,y1,x2,y2` | 동일 |
| `thickness`, `height` | 동일 |
| `role` | 동일 (`"inner"` \| `"outer"` 만 허용) |
| `material` | `material` (enum: `concrete`, `glass`, `wood`, `metal`, `unknown`) |

레거시로 `material_id` + 외부 맵만 있는 경우는 `scene_graph_to_rf_scene_dict` 경로에서 처리한다. DTO 직접 경로에서는 `material` 문자열을 쓴다.

## 개구 `Opening`

DTO는 선분 `(x1,y1)–(x2,y2)`와 `wall_ref`(벽 `id`)를 준다. RF canonical은 GeoJSON `line_geom`(LineString)과 `wall_id`를 쓴다.

| DTO | RF |
|-----|-----|
| `id` | `id` |
| `type` | `opening_type` |
| `wall_ref` | `wall_id` |
| `x1..y2` | `line_geom`: LineString coordinates |
| (선분 길이) | `width_m` (퇴화 시 최소 0.01m) |
| — | `version_id` = 씬의 `scene_version`과 동일 |

## 방 `Room`

| DTO | RF |
|-----|-----|
| `id` | `id`, 그리고 `room_name` 기본값으로 동일 id 사용 |
| `points` | `polygon_geom` 외곽 링 (닫힌 링으로 정규화) |
| `center` | `centroid_geom` Point |
| `area` | `area_m2` |
| — | `space_type`: `"room"` (고정) |
| — | `version_id` = 씬 `scene_version` |

## 객체 `objects`

DTO의 각 원소는 **dict** 여야 하며 내용은 그대로 RF `objects[]`에 복사된다 (baseline은 footprint 등 선택적 해석).

## 확인 사항 (합의)

- **`role`**: 스키마상 `inner` / `outer` 만.
- **`material`**: 위 enum 다섯 가지 (`schemas/backend_scene_schema.json` 과 맞춤).
- **좌표**: `units == "m"` 일 때만 RF 입력으로 사용 (meter).

## 샘플

- `sample/backend_scene_graph_example.json` — floorplan DTO JSON
- `sample/rf_scene_from_backend.json` — `export_rf_from_backend_sample.py` 출력
