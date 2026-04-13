# RF 씬 입력 Handoff Spec (백엔드 ↔ AI/RF)

**목적:** canonical scene graph에서 확정된 씬을 RF baseline 시뮬레이터로 넘길 때 **필드·형식·식별자 규칙**을 팀 합의로 고정한다.  
**구현 기준:** `app/rf/models/rf_models.py`의 `Scene.from_dict` / `Wall` / `Opening` / `Room` 파서 (2025 캡스톤 baseline).

**좌표:** 단일 층 **floor-local**, 단위 **미터(m)**. 원점·축 방향은 프로젝트 전역 규칙과 일치해야 한다.

---

## 1. 루트 객체 (Scene payload)

HTTP 경로의 `project_id` / `floor_id` / `scene_version_id`와 별개로, **RF 본문에 아래를 둘지** 합의가 필요하다.

| 필드 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `units` | **MUST** | `"m"` | RF baseline은 현재 `"m"`만 허용. |
| `sourceType` | **MUST** | string | 데이터 출처 식별(파이프라인 이름 등). `scene_version_id`가 없을 때 RF 내부 식별자 fallback으로 쓰일 수 있음. |
| `walls` | **MUST** | array | 벽 객체 목록. |
| `openings` | **MUST** | array | 개구부 목록(없으면 `[]`). |
| `rooms` | **MUST** | array | 방/공간 목록(없으면 `[]`). |
| `objects` | **MUST** | array | 3D 배치물 등. baseline RF는 **내용을 사용하지 않으나** 스키마상 배열 필수. 없으면 `[]`. |
| `scene_version_id` | **SHOULD** | string | 시뮬·AP layout·config와 **동일 문자열**로 맞출 것. 없으면 RF는 `sourceType`으로 대체(비권장). |
| `floor_id` | **OPTIONAL** | string | 영속·로그용. RF 시뮬 수학에는 미사용. |

**합의 권장:** 백엔드는 `GET .../scene-versions/{id}` 응답 본문에 **`scene_version_id` + `floor_id`** 를 항상 넣고, 경로 파라미터와 **동일 값**이 되게 한다.

---

## 2. Wall (벽)

### 2.1 최종 JSON 형태 (필드 단위)

| 필드 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `id` | **MUST** | string | 벽 고유 ID. opening의 `wall_id`가 참조. |
| `x1`, `y1`, `x2`, `y2` | **MUST** | number | 벽 **중심선** 양끝 (floor-local m). |
| `thickness` | **MUST** | number | 두께 (m), &gt; 0. |
| `height` | **MUST** | number | 높이 (m), &gt; 0. |
| `role` | **MUST** | `"outer"` \| `"inner"` | 외벽/내벽. RF 내부에서는 `exterior` / `interior`로 매핑. |
| `material` | **OPTIONAL** | string | 아래 §4 참고. 없으면 role 기본값. |
| `version_id` | **OPTIONAL** | string | 없으면 루트 `scene_version_id`와 동일하게 취급. |

**비고:** 백엔드 DB가 폴리라인/다각형만 가질 경우, RF로 넘기기 전에 **중심선 양끝**으로 변환하는 책임 주체(백엔드 vs 어댑터)를 정한다.

---

## 3. Opening (개구부)

### 3.1 RF가 현재 요구하는 형식 (GeoJSON)

| 필드 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `id` | **MUST** | string | 개구부 ID. |
| `version_id` | **MUST** | string | 보통 `scene_version_id`와 동일. |
| `wall_id` | **MUST** | string | 반드시 존재하는 `walls[].id`와 일치. |
| `opening_type` | **MUST** | string | 예: `door`, `window` (RF는 문자열로만 구분, baseline 감쇠 차등은 없음). |
| `line_geom` | **MUST** | object | **GeoJSON `LineString`**, `coordinates`에 **정확히 2점** `[[x1,y1],[x2,y2]]` (벽 상 개구부 축). |
| `width_m` | **MUST** | number | &gt; 0. |
| `sill_height_m` | **OPTIONAL** | number | 바닥 기준. |
| `head_height_m` | **OPTIONAL** | number | sill &lt; head 검증 있음. |

**합의 필요:** 백엔드가 `pos_x`, `pos_y`, `width`, `height`만 줄 경우, **RF로 넘기기 전에** `line_geom` + `wall_id`를 채우는 변환 규칙을 정한다.  
**RF baseline은** (현재) `line_geom` 외 opening 표현을 파싱하지 않는다.

---

## 4. Material: 문자열 vs `material_id`

| 방식 | 설명 | RF baseline (현재) |
|------|------|---------------------|
| **A. 문자열 키** | 백엔드 스키마 enum: `concrete`, `glass`, `wood`, `metal`, `unknown` (`schemas/backend_scene_schema.json`) | **지원.** `rf_materials.DEFAULT_MATERIAL_PROFILES` 키와 일치하면 `attenuation_db` 적용. 미등록 키는 **`unknown`과 동일 손실로 폴백**. 레거시 `drywall` 키는 호환용으로 등록 유지. |
| **B. `material_id` (UUID 등)** | DB FK | **직접 파싱 안 함.** 백엔드 또는 BFF에서 **`material_id` → 위 문자열 키**로 해석한 뒤 RF JSON에는 **해석된 문자열**을 `material`에 넣거나, 별도 `material_profile_key` 필드를 **합의 후** 추가해 확장한다. |

**합의 권장 (단기):** RF JSON에는 **`material` 문자열**만 넣고, 값은 팀이 정한 **닫힌 집합**으로 제한. `material_id`는 백엔드 내부 저장용으로 두고, **handoff 직전에 resolve**.

---

## 5. Room (공간)

| 필드 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `id` | **MUST** | string | |
| `version_id` | **MUST** | string | |
| `room_name` | **MUST** | string | |
| `space_type` | **MUST** | string | 예: `room`, `corridor` (후보 휴리스틱에 사용). |
| `polygon_geom` | **MUST** | GeoJSON `Polygon` | 외곽 링, **닫힌 링**(첫 점=마지막 점), floor-local m. |
| `centroid_geom` | **OPTIONAL** | GeoJSON `Point` | |
| `area_m2` | **OPTIONAL** | number | |

**centroid 합의:**

- **백엔드가 줄 수 있으면:** `centroid_geom` 포함 권장(일관성).
- **없으면:** RF 후보 생성 쪽은 **다각형 꼭짓점 평균**으로 대체 가능(현재 `ap_candidate_generator.get_room_centroid` 동작).

즉, **MUST는 polygon**이고, centroid는 **SHOULD(백엔드) / RF 대체 가능**.

---

## 6. 식별자·버전 정리

| 식별자 | 위치 | 권장 |
|--------|------|------|
| `scene_version_id` | 루트, SHOULD | API의 `scene_version` 리소스 id와 동일 문자열. |
| `floor_id` | 루트, OPTIONAL | URL `floor_id`와 동일. |
| `version_id` (wall/room/opening) | 각 요소 | `scene_version_id`와 같게 통일하면 디버깅 유리. |

---

## 7. 백엔드와 체크할 합의 체크리스트

- [ ] 루트에 `scene_version_id` / `floor_id`를 넣는지, 넣는다면 경로 파라미터와 동일한지  
- [ ] 벽은 **중심선 `x1,y1,x2,y2`** 로 통일했는지  
- [ ] opening은 **`line_geom` LineString 2점 + 유효한 `wall_id`** 인지  
- [ ] `material`은 **문자열 프로파일 키**로 줄지, `material_id`만 온다면 **누가 어디서 resolve**하는지  
- [ ] room은 **`polygon_geom` 필수**인지, centroid는 백엔드 제공 vs RF 계산 중 무엇을 채택할지  
- [ ] 단위는 항상 **`units: "m"`** 인지  

---

## 8. 참고: 구현 파일

- 파서: `app/rf/models/rf_models.py` (`Scene`, `Wall`, `Opening`, `Room`)
- 재질 프로파일: `app/rf/rf_materials.py`
- 샘플: `app/rf/sample/rf_scene_input_complex.json`

이 문서는 **합의서**이며, 필드 추가/변경 시 본 문서 버전과 `rf_models`를 함께 갱신한다.
