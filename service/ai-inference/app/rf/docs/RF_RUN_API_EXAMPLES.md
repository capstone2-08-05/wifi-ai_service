# `POST /internal/rf/run` 요청·응답 예시

기본 URL: `http://127.0.0.1:8000` (uvicorn 실행 시)

---

## 1) `sionna_dto` (floorplan `SceneSchema` + 안테나 + 솔버 설정)

**요청**

```json
{
  "engine": "baseline",
  "run_type": "preview",
  "floor_id": "floor_01",
  "baseline": {
    "grid_resolution_m": 0.25,
    "path_loss_constant_db": 63.0,
    "path_loss_exponent": 2.0,
    "include_exterior_walls": false,
    "output_dir_name": "output",
    "antenna_z_policy": "ignore",
    "default_antenna_z_m": 2.5,
    "layout_name": "api_manual",
    "layout_type": "manual",
    "skip_heatmap": false
  },
  "input": {
    "kind": "sionna_dto",
    "data": {
      "config": {
        "frequency_ghz": 5.0,
        "tx_power_dbm": 20.0,
        "reflection_order": 2
      },
      "antenna": {
        "tx_id": "ap_001",
        "position_m": [1.0, 2.0, 2.5]
      },
      "scene": {
        "scene_version": "sv_demo_backend_v1",
        "units": "m",
        "sourceType": "floorplan",
        "walls": [
          {
            "id": "w1",
            "x1": 0.0,
            "y1": 0.0,
            "x2": 4.0,
            "y2": 0.0,
            "thickness": 0.2,
            "height": 2.8,
            "role": "outer",
            "material": "concrete"
          }
        ],
        "openings": [],
        "rooms": []
      }
    }
  }
}
```

**응답 (성공 시, 일부 생략)**

```json
{
  "rf_run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "succeeded",
  "metrics": {
    "scene_version_id": "sv_demo_backend_v1",
    "layout_name": "api_manual",
    "grid": { "resolution_m": 0.25, "x_count": 17, "y_count": 5, "point_count": 85 },
    "rssi_summary": { "min_dbm": -59.0, "max_dbm": -23.0, "mean_dbm": -48.0 }
  },
  "artifacts": {
    "strongest_rssi_map": "strongest_rssi_map.npy",
    "strongest_path_loss_map": "strongest_path_loss_map.npy",
    "strongest_wall_loss_map": "strongest_wall_loss_map.npy",
    "best_server_map": "best_server_map.npy",
    "per_ap_rssi_maps": { "ap_001": "rssi_map_ap_001.npy" },
    "heatmap_png": "strongest_rssi_heatmap.png"
  },
  "output_root": "C:\\\\...\\\\data\\\\rf\\\\runs\\\\550e8400-...",
  "detail": null
}
```

---

## 2) `rf_canonical` (이미 adapter 통과한 RF scene + layout + sim_config)

**요청**

```json
{
  "engine": "baseline",
  "run_type": "preview",
  "baseline": {
    "grid_resolution_m": 0.25,
    "path_loss_constant_db": 63.0,
    "path_loss_exponent": 2.0,
    "include_exterior_walls": false,
    "output_dir_name": "output"
  },
  "input": {
    "kind": "rf_canonical",
    "scene": {},
    "ap_layout": {},
    "sim_config": {
      "scene_version_id": "sv_demo_backend_v1",
      "grid_resolution_m": 0.25,
      "path_loss_constant_db": 63.0,
      "path_loss_exponent": 2.0,
      "include_exterior_walls": false,
      "output_dir_name": "output"
    }
  }
}
```

(`scene` / `ap_layout` 은 `sample/rf_scene_from_backend.json`, `sample/ap_layout_backend_demo.json` 형식을 채워 넣는다.)

---

## 저장 위치

- 환경 변수 `RF_STORAGE_ROOT` 미설정 시: `service/ai-inference/data/rf/`
  - `runs/<rf_run_id>/output/` — `run_manifest.json`, `.npy`, heatmap PNG
  - `persistence/` — `rf_runs.json`, `ap_layouts.json`, `rf_maps.json`
