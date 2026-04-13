# Baseline: 재질(material) · 개구부(opening) 규칙

대상: `BaselineRfSimulator`, `rf_models.Wall` / `Opening`, `MaterialProfileRegistry`.

**서비스 메시지:** 사용자에게 보이는 설명은 **2D floorplan** 위에서 **재질·창문(개구)·가구 영역**이 수신 품질에 어떻게 반영되는지로 가져간다. (3D 뷰가 아니라 **도면·heatmap 중심**; 제품 역할 요약은 `docs/SCENE_GRAPH_ADAPTER_MAPPING.md` 서문.)

## 규칙 표 — 재질

| 단계 | 입력 | Baseline 해석 |
|------|------|----------------|
| Scene 파싱 | `Wall`에 `material` 문자열 | `rf_models`가 비어 있으면 역할별 기본값 (`outer`→concrete, `inner`→**unknown**) |
| Scene 파싱 | `material` 비어 있음 | 위 기본값 |
| 시뮬 합산 | `wall.material` (문자열) | `MaterialProfileRegistry.get_loss_db(name)` → 등록 키면 `attenuation_db`, **미등록 키는 `unknown`과 동일 손실로 폴백** |
| DTO `material_id`만 있는 경우 | adapter 밖에서 해석 | `scene_to_rf_adapter`가 `material_id_to_profile_key`로 **`material` 문자열**을 채운 뒤 RF로 전달 |

**정리:** Baseline 엔진은 **`material_id`를 모른다.** 항상 RF JSON의 **`material` 프로파일 키**만 본다. ID→키 변환은 adapter(또는 백엔드 사전 처리) 책임.

백엔드 합의 스키마(`schemas/backend_scene_schema.json`): 벽 `material` enum은 **`concrete` \| `glass` \| `wood` \| `metal` \| `unknown`**.  
등록 프로파일·dB 예: `rf_materials.DEFAULT_MATERIAL_PROFILES` (레거시 `drywall` 키 호환 유지).

## 규칙 표 — 외벽 스킵

| 설정 | 동작 |
|------|------|
| `SimulationConfig.include_exterior_walls == False` | `role`이 외곽에 해당하는 벽(`outer`)은 **벽 손실 합산에서 제외** |
| `True` | 외벽도 교차 시 `get_loss_db`만큼 가산 |

## 규칙 표 — 개구부(opening)와 벽 손실

1. AP–수신 격자점 직선이 벽 선분과 교차하는지 검사한다.
2. 교차하면, 그 벽 ID에 대해 **개구부 목록**을 본다 (`opening.wall_id`로 그룹).
3. **동일 직선**이 어떤 개구부의 선분(`opening.start`–`opening.end`, `line_geom`에서 온 2D 선분)과도 교차하면 → 그 벽에 대해 **벽 재질 손실을 적용하지 않는다** (해당 링크에서 “문/창 통과”로 간주).

주의:

- 개구부 기하는 **벽 ID에 매달려야** 하며, `line_geom`은 그 벽 위의 **선분**이어야 한다.
- Baseline은 **주파수/창 유리 두께 등 미세 모델링 없음**; 개구부면 구간 전체를 링크당 한 번만 “통과” 처리한다.

## 가구·장애물 (preview, 최소)

`Scene.objects[]`에서 아래 형태만 baseline이 **추가 감쇠**로 해석한다 (`_compute_furniture_clutter_db`, 합산 상한 약 25 dB).

```json
{
  "id": "desk_01",
  "kind": "furniture_preview",
  "footprint_m": { "min_x": 1.0, "max_x": 2.2, "min_y": 0.5, "max_y": 1.0 },
  "attenuation_db": 3.0
}
```

- 수신 격자점 \((x,y)\)가 `footprint_m` 안이면 `attenuation_db`를 합산해 RSSI에서 감산.
- Sionna에 3D 가구 메시를 넣는 것은 별도; preview는 2D clutter, precise는 내부 엔진에서 확장.

## 코드 위치 (참고)

- 벽 손실 합산: `baseline_rf_simulator.BaselineRfSimulator._compute_wall_loss`
- 개구부 예외: `_line_of_sight_uses_opening`
- 가구 clutter: `_compute_furniture_clutter_db`
- 재질 dB: `MaterialProfileRegistry.get_loss_db` (`rf_materials.py`)
