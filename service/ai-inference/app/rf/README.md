# RF Baseline Preview Simulator

- 입력은 `scene`과 `ap layout`으로 분리
- `scene`은 `confirmed scene_version` 기준 canonical JSON 사용
- 좌표계는 single-floor, meter 단위 고정
- baseline 단계에서는 **거리 기반 path loss + 재질 기반 wall loss** 적용
- `opening`이 있으면 해당 wall 교차 시 감쇠를 제거
- 출력은 `.npy` 행렬, `.png` heatmap, `run_manifest.json` 메타데이터로 저장

## 디렉터리 구조 (요약)

```text
app/rf/
├─ models/           # rf_models (Scene, ApLayout, …)
├─ materials/        # 재질 매핑·프로파일
├─ rules/            # objects[] 장애물 규칙
├─ simulation/       # baseline_rf_simulator
├─ persistence/      # JSON 프로토타입 저장
├─ layout/           # AP 후보·레이아웃 빌드
├─ conversion/       # scene_to_rf_adapter
├─ dto/              # 백엔드 합의 DTO
├─ adapters/         # Baseline / Sionna 변환
├─ services/         # run_rf (API 진입)
├─ fixtures/         # golden 씬 등
├─ scripts/          # CLI 데모·샘플 export
├─ sionna_poc/       # Sionna RT PoC
├─ tests/ · sample/ · docs/
└─ README.md
```

## 실행 방법 (Baseline CLI)

`ai-inference` 서비스 루트에서, `PYTHONPATH`에 현재 디렉터리가 잡혀 있다고 가정:

```bash
python -m app.rf.simulation.baseline_rf_simulator \
  --scene app/rf/sample/rf_scene_input.json \
  --layout app/rf/sample/ap_layout_input.json \
  --config app/rf/sample/sim_config.json
```

## 출력 파일

실행 후 `sample/output/` 아래에 아래 파일이 생성됨

- `strongest_rssi_map.npy`
- `strongest_path_loss_map.npy`
- `strongest_wall_loss_map.npy`
- `best_server_map.npy`
- `rssi_map_ap_001.npy` 같은 AP별 RSSI 맵
- `strongest_rssi_heatmap.png`
- `run_manifest.json`

## 현재 범위

- 단일 층 2D
- strongest AP 기준 RSSI preview
- 단순 path loss
- 벽 재질 감쇠
- opening 반영

## 제외 항목

- multi-floor
- diffraction / reflection
- SINR / interference
- calibration
- detailed furniture loss
- full 3D ray tracing

## 문서 (핵심만)

| 파일 | 내용 |
|------|------|
| `RUNBOOK.md` | 데모·발표 산출물·Sionna 실행 |
| `docs/RF_SCENE_HANDOFF_SPEC.md` | RF JSON 합의 |
| `docs/SCENE_GRAPH_ADAPTER_MAPPING.md` | DTO·어댑터·제품 방향 |
| `docs/RF_MATERIAL_AND_OPENING_RULES.md` | 재질·개구·가구 preview |
