# Scene graph DTO → RF canonical 매핑

## 0) 합의 백엔드 DTO (권장)

Pydantic 모델: `app/rf/backend_scene_dto.py`  
**동일 DTO**를 쓰되, 엔진별로 **어댑터를 둘로 나눈다.**

| 모듈 | 용도 |
|------|------|
| `adapter_baseline_dto.py` | **Baseline RF** — 2D floorplan, 벽/개구/재질은 `RF_MATERIAL_AND_OPENING_RULES`·`baseline_rf_simulator` 규칙. 안테나는 기본적으로 **x,y만** 쓰고 `z`는 `ignore` 또는 `default_z_m` (또는 `use_position_z`로 참고). |
| `adapter_sionna_dto.py` | **Sionna RT** — 벽 **높이·두께**, 안테나 **(x,y,z)**, `frequency_ghz`·`tx_power_dbm`·`reflection_order`→솔버, `material`→**ITU 재질명** 매핑 스냅샷. |

### Baseline (`adapter_baseline_dto`)

| 진입점 | 설명 |
|--------|------|
| `scene_schema_to_baseline_rf_scene_dict(SceneSchema)` | Baseline용 RF 루트 dict |
| `sionna_input_dto_to_baseline_scene_and_layout(SionnaInputDTO, antenna_z_policy=…)` | (scene, 수동 AP layout); 기본 `antenna_z_policy="ignore"` |
| `antenna_dto_to_baseline_ap_layout_dict(..., z_policy="ignore"\|"use_position_z")` | 단일 AP |

`scene_to_rf_adapter.scene_schema_to_rf_scene_dict` = 위 baseline 씬 변환과 동일(별칭).  
`antenna_dto_to_ap_layout_dict` = **하위 호환**으로 `z_policy="use_position_z"` (기존 동작).

### Sionna (`adapter_sionna_dto`)

| 진입점 | 설명 |
|--------|------|
| `scene_schema_to_sionna_scene_plan(SceneSchema)` | 벽·개구·방 + `itu_radio_material` |
| `sionna_input_dto_to_engine_plan(SionnaInputDTO)` | 씬 계획 + 안테나 3D + `solver.max_depth` 등 JSON 스냅샷 |

`scene_to_rf_adapter.sionna_input_dto_to_sionna_engine_plan` = 래퍼.

| 백엔드 필드 | Baseline RF | Sionna 계획 |
|-------------|------------|-------------|
| `SceneSchema.scene_version` | `scene_version_id` | `scene_version` + 동일 스키마 |
| `Wall` | `x1..y2`, `material`→baseline 키 | + `height_m`, `itu_radio_material` |
| `Opening` | `line_geom` + `wall_id`←`wall_ref` | 2D 세그 + `wall_ref` |
| `AntennaDTO.position_m` | 기본 z 무시·`default_z_m` | 전부 **x,y,z** |
| `SimConfigDTO` | `tx_power_dbm`, `frequency_ghz` (AP) | + `reflection_order`→`max_depth` |

레거시 JSON(dict)는 `scene_graph_to_rf_scene_dict()` 유지 (`sample/backend_scene_graph_example.json` 등).

---

`scene_to_rf_adapter.scene_graph_to_rf_scene_dict()` 기준(레거시). 백엔드 canonical DTO와 필드명이 다르면 **adapter 안의 `_first_str` 별칭 목록**만 조정하면 된다.

**제품 방향:** 변환 결과는 **단일 층 2D floorplan** 기준 RF 입력으로 쓴다. 사용자 UI는 **heatmap·AP·재질/창문/가구** 설명이 중심이며, 3D 전파 뷰가 전면이 아니다 (`docs/SERVICE_RF_ARCHITECTURE.md`).

## 입력 DTO 예시 (레거시 dict)

- 파일: `sample/backend_scene_graph_example.json`
- 의도: 혜승 쪽에서 내려올 수 있는 **camelCase + `material_id`** 혼합 예시.

## 루트 필드

| RF 출력 키 | DTO 예시 키 | 비고 |
|------------|-------------|------|
| `scene_version_id` | `sceneVersionId`, `version_id` | 필수 |
| `floor_id` | `floorId` | 선택 |
| `sourceType` | `sourceType`, `source_type` | 없으면 인자 `source_type=` 필수 |
| `units` | (고정) | 항상 `"m"` (다른 단위는 거부) |
| `walls` | `walls` | 리스트 |
| `openings` | `openings` | 리스트 |
| `rooms` | `rooms` | 리스트 |
| `objects` | `objects` | 없으면 `[]` |

## 벽 (wall)

| 의미 | RF / adapter | DTO 예시 |
|------|--------------|----------|
| ID | `id` | `id` / `wall_id` / `wallId` |
| 역할 | `role` `outer` \| `inner` | 동일 |
| 기하 | `x1`…`y2`, `thickness`, `height` | 동일 |
| 재질 문자열 | `material` | 있으면 그대로 RF로 |
| 재질 ID | `material_id` | `material_id_to_profile_key`로 `concrete` 등으로 변환 |

## 개구부 (opening)

| 의미 | RF | DTO 예시 |
|------|-----|----------|
| ID | `id` | `id` / `opening_id` / `openingId` |
| 벽 참조 | `wall_id` | `wall_id` / `wallId` |
| GeoJSON | `line_geom` LineString (2점) | 동일 |
| `version_id` | 없으면 씬 `scene_version_id`로 채움 | `version_id` / `versionId` |

## 방 (room)

| 의미 | RF | DTO 예시 |
|------|-----|----------|
| ID | `id` | `id` / `room_id` / `roomId` |
| 이름 | `room_name` | `room_name` / `roomName` / `name` |
| 유형 | `space_type` | `space_type` / `spaceType` |
| 폴리곤 | `polygon_geom` Polygon | 동일 |
| `version_id` | 없으면 씬과 동일 | 선택 |

## `material_id` 해석표 (샘플)

백엔드가 UUID/코드를 줄 때 RF 프로파일 키로 매핑한다. 예시 파일: `sample/backend_material_id_map.json`.

| material_id (예시) | RF `material` (프로파일 키) |
|----------------------|------------------------------|
| `MAT_CONCRETE_01` | `concrete` |
| `MAT_DRYWALL_01` | `unknown` (스키마 enum; 레거시로 `drywall` 키도 `rf_materials`에 유지) |
| `MAT_GLASS_01` | `glass` |

운영에서는 DB 조회 또는 설정으로 같은 역할을 한다.

## 출력 RF JSON 샘플

- `sample/rf_scene_from_backend.json` (`export_rf_from_backend_sample.py`로 재생성)

## 아직 확정 전(TBD)으로 두는 것

| 항목 | 상태 |
|------|------|
| DTO 루트 스키마 버전 (`schema`) | 예시만 있음; 혜승 스펙 확정 시 adapter는 무시 가능 |
| `objects[]` 형식 | RF는 `Scene.from_dict`가 dict 리스트로만 검증; 필드 미사용 |
| `material_id` 전체 목록 | 팀 DB/디자인 시스템과 합의 필요 |
| 단위 `units` ≠ m | 현재 미지원 |

## Baseline까지 연결 (검증)

```powershell
cd service/ai-inference/app/rf
python export_rf_from_backend_sample.py
python run_backend_baseline_demo.py
```
