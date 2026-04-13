# Baseline 재질(material) · 개구(opening) 규칙 (최종)

대상 코드: `BaselineRfSimulator`, `app.rf.models.rf_models`의 `Wall` / `Opening`, `MaterialProfileRegistry`, `app.rf.materials.material_mapping`, Sionna 어댑터(`app.rf.adapters.sionna`).

제품 메시지: **2D floorplan** 위에서 재질·창문·가구가 수신 품질(heatmap)에 어떻게 반영되는지 설명한다.

---

## 1. 백엔드 벽 `material` enum (혜승 DTO / `app/schemas/floorplan.py`)

허용 문자열 (소문자):

`concrete` | `glass` | `wood` | `metal` | `unknown`

- 스키마에 **`drywall` 없음**. 과거 RF/데모에서 쓰던 `drywall` 문자열은 **`material_mapping.normalize_wall_material_key`** 에서 **`wood`** 로 정규화한다 (경량 내벽·칸막이 티어 통합).
- `plasterboard` 원문은 ITU 재질 이름과 혼동될 수 있어, Baseline 티어는 **`wood`** 로 정규화한다.

---

## 2. Baseline: 재질별 추가 손실 (참고 주파수 5 GHz, 1회 교차당 dB)

`rf_materials.DEFAULT_MATERIAL_PROFILES` / `MaterialProfileRegistry.get_loss_db` 가 사용한다.  
값은 **preview용 단순 랭킹**이며, 실측·주파수 보정은 후속 튜닝 대상이다.

| 티어 (의도) | enum | `attenuation_db` | 비고 |
|-------------|------|------------------|------|
| 매우 큰 손실 | `metal` | **18** | 금속 구조·차폐에 가까운 가정 |
| 큰 손실 (고손실) | `concrete` | **12** | 구조체·외벽 등 |
| 중간 | `glass` | **6** | 유리·유사 투명 면 |
| 중간 이하 | `wood` | **5** | 목재·내벽; `drywall` 정규화 결과도 여기 |
| 폴백 | `unknown` | **4** | 미지정·저신뢰·스키마 밖 문자열 정규화 결과 |

**정렬 (손실 큰 순):** `metal` (18) > `concrete` (12) > `glass` (6) > `wood` (5) > `unknown` (4).

### 2.1 `unknown` 처리

- DTO에서 `material` 생략 시 `rf_models` 기본: `outer` → `concrete`, `inner` → `unknown` (역할별 기본).
- 임의 문자열·미등록 키는 `normalize_wall_material_key` → **`unknown`** → 위 표의 **4 dB** (미등록 키 직접 조회도 동일 폴백).
- `material_id` 만 있는 JSON은 adapter 밖에서 `material_id_to_profile_key` 로 **enum 문자열**을 채운 뒤 RF로 넘긴다 (Baseline은 ID 자체를 보지 않음).

### 2.2 코드 진입점

- 정규화: **`material_mapping.normalize_wall_material_key`**
- dB 조회: **`material_mapping.get_baseline_wall_loss_db`** 또는 `MaterialProfileRegistry.get_loss_db` (내부에서 정규화).

---

## 3. 개구부(opening)와 벽 손실 (Baseline)

구현: `BaselineRfSimulator._compute_wall_loss`, `_line_of_sight_uses_opening`.

1. AP–수신 격자점 직선이 벽 선분과 **교차**하는지 검사한다.
2. 교차한 벽에 대해, **같은 직선**이 그 벽에 속한 어떤 **개구부 선분**(`opening.start`–`opening.end`, DTO의 `x1..y2`에서 유도)과도 교차하면, **그 벽에 대한 재질 손실을 이번 링크에서 가산하지 않는다** (문/창 “통과”로 간주).
3. 개구부는 반드시 `wall_id`(DTO `wall_ref`)로 벽에 매달려 있어야 하며, 선분은 그 벽 위에 있어야 한다.

**한계 (의도):**

- 주파수·유리 종류·틀 두께 등 **미세 모델 없음**.
- 한 벽을 여러 번 가로지르는 LOS에 대한 고급 처리 없음 (preview).

---

## 4. Baseline vs Sionna 의미 체계

| 구분 | Baseline | Sionna (ITU RadioMaterial) |
|------|----------|----------------------------|
| 입력 | enum(또는 정규화 결과) 문자열 | `map_baseline_material_to_sionna_itur` 로 ITU 이름 |
| 물리 | 고정 dB 가산(2D) | 엔진 내 ITU 재질 모델 (별도) |
| 목표 | **동일 enum 티어 순서**가 두 경로에서 맞도록 매핑표 유지 | |

`material_mapping.BASELINE_TO_SIONNA_ITU` 예:

- `concrete`→`concrete`, `glass`→`glass`, `wood`→`wood`, `metal`→`metal`
- `unknown`→`plasterboard` (ITU 쪽 중간 내벽 계열; Baseline `unknown` dB와 수치 동기화는 튜닝 가능)

레거시 원문 `brick`, `marble` 등은 enum에 없으면 Baseline은 **`unknown`** 으로 정규화되나, Sionna 전용으로 `LEGACY_EXTRA_TO_SIONNA_ITU` 에 있으면 **원문 우선**으로 ITU 이름을 잡을 수 있다 (구 JSON 호환).

---

## 5. 외벽 스킵 · objects(가구) 장애물

| 설정 | 동작 |
|------|------|
| `SimulationConfig.include_exterior_walls == False` | `role == outer` 인 벽은 벽 손실 **합산 제외** |
| `objects[]` | AP–수신 직선이 2D footprint 와 겹치면 추가 감쇠 (합산 상한). 상세는 **`docs/BASELINE_OBJECTS_OBSTACLE_RULES.md`**, 스키마 메모는 **`docs/OBJECTS_FURNITURE_SCHEMA.md`**. |

---

## 6. 코드 위치

| 항목 | 위치 |
|------|------|
| enum 정규화·Sionna 매핑 | `material_mapping.py` |
| dB 프로파일 | `rf_materials.py` |
| 벽 손실 / 개구 예외 | `app/rf/simulation/baseline_rf_simulator.py` |
| objects LOS 장애물 | `object_obstacle_rules.py`, `BaselineRfSimulator._compute_obstacle_loss_on_los` |
| DTO → Sionna 스냅샷 | `app/rf/adapters/sionna.py` |
