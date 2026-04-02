# RF Baseline Preview Simulator

- 입력은 `scene`과 `ap layout`으로 분리
- `scene`은 `confirmed scene_version` 기준 canonical JSON 사용
- 좌표계는 single-floor, meter 단위 고정
- baseline 단계에서는 **거리 기반 path loss + 재질 기반 wall loss** 적용
- `opening`이 있으면 해당 wall 교차 시 감쇠를 제거
- 출력은 `.npy` 행렬, `.png` heatmap, `run_manifest.json` 메타데이터로 저장

## 파일 구조

```text
rf_baseline_v2/
├─ baseline_rf_simulator.py
├─ rf_models.py
├─ rf_materials.py
├─ README.md
└─ sample/
   ├─ rf_scene_input.json
   ├─ ap_layout_input.json
   └─ sim_config.json
```

## 실행 방법

```bash
python baseline_rf_simulator.py \
  --scene sample/rf_scene_input.json \
  --layout sample/ap_layout_input.json \
  --config sample/sim_config.json
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
