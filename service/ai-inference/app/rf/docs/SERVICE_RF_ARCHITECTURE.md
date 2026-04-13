# RF 서비스 구조 (2D floorplan 중심)

## 사용자에게 보이는 것

- **2D floorplan** 위 **heatmap**(RSSI / coverage), **AP 후보·배치**, **벽·재질·창문(개구)·가구 영역**에 따른 품질 설명.
- “3D 뷰어로 도는 Wi-Fi 서비스”가 아니라, **평면 도면 기반으로 품질을 설명**하는 제품 방향이다.

## 엔진 역할 분리

| 엔진 | 역할 | 사용 시점 |
|------|------|-----------|
| **Baseline** (`BaselineRfSimulator`) | **빠른 preview** — 후보 비교, 레이아웃 반복, 실시간에 가까운 재시뮬 | 사용자 플로우 기본 |
| **Sionna RT** | **내부 precise 검증** — 레이 트레이싱 기반 정밀 분석(필요 시·배치) | 동일 RF 입력 축에서 정밀도를 보완할 때 |

- **Sionna의 3D 기하·전파 계산**은 **제거하지 않는다.** 다만 **UI/서비스 메시지의 전면**이 아니라, **내부 정밀 엔진**으로 둔다.
- 사용자 산출물의 기본은 **2D 격자 heatmap·지표**이다.

## 입력 스토리

품질 차이 설명의 중심은 다음이다.

1. **재질(material)** — 벽·구획의 감쇠  
2. **창문·문(opening)** — LOS가 개구를 지나면 해당 벽 감쇠 완화  
3. **가구·장애물** — (baseline에서는 `objects` 기반 **발 위치 clutter** 등 최소 모델, 문서: `RF_FURNITURE_PREVIEW.md`)

## 참고 문서

- `RF_SCENE_HANDOFF_SPEC.md` — RF JSON  
- `RF_MATERIAL_AND_OPENING_RULES.md` — 재질·개구  
- `SCENE_GRAPH_ADAPTER_MAPPING.md` — DTO → RF  
- `SIONNA_RUNBOOK.md` — Sionna 실행(내부 검증용)
