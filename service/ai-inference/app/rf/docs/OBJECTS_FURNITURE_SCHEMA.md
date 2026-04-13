# `objects[]` 스키마 메모 (RF handoff 최소안)

목적: **3D 가구 메시 없이** 2D 바닥 투영 + 추가 감쇠만으로 “가구 배치에 따라 품질이 달라진다”를 설명·데모한다.

백엔드 `SceneSchema.objects` 는 `List[Any]` 이므로, 아래는 **RF 팀 합의 최소 필드**이며 Baseline이 해석하는 키를 나열한다.

## 권장 필드

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `id` | string | 권장 | 객체 식별 (로그·UI) |
| `type` | string | 권장 | `obstacle_class` 와 동일 계열 (`furniture_heavy`, `clutter`, …). 미지정 시 `obstacle_class` / `material` 로 손실 추정 |
| `footprint_m` 또는 `bbox_m` | object | **둘 중 하나** | 축정렬 사각형 (meter): `min_x`, `max_x`, `min_y`, `max_y` |
| `points` | `[[x,y], ...]` | 대안 | 바닥 투영 다각형 꼭짓점. Baseline preview 에서는 **AABB**(min/max)만 사용 |
| `height` 또는 `height_m` | number | 선택 | 3D·Sionna 확장용 메모; **Baseline 2D 경로에서는 미사용** |
| `material` | string | 선택 | **가구 재질** 분류 (`wood`, `metal`, …). 벽 `Wall.material` enum 과 이름이 겹칠 수 있으나 **의미는 별도** (장애물 전용 테이블) |
| `obstacle_class` | string | 선택 | `type` 과 동일 우선순위로 손실 기본값 조회 (`object_obstacle_rules.DEFAULT_OBSTACLE_CLASS_DB`) |
| `attenuation_db` | number | 선택 | 해당 객체에 대한 **추가 손실 [dB]** (명시 시 클래스/재질 기본값보다 우선) |

## Baseline이 쓰는 최소 조합

1. **2D 영역**: `footprint_m` / `bbox_m` **또는** `points` 로부터 계산한 AABB  
2. **손실 크기**: `attenuation_db` **또는** `obstacle_class` / `type` / `material` 기본값

## 예시 JSON

`sample/scene_with_objects_example.json` 참고.
