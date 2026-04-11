# 발표용 RF 산출물 (고정 스냅샷)

동일 씬·동일 `sim_config_complex.json`에서 **AP 배치만** 달리한 결과입니다.

| 항목 | 경로 |
|------|------|
| 단일 AP 히트맵 | `01_manual_single_ap/strongest_rssi_heatmap.png` |
| 단일 AP manifest | `01_manual_single_ap/run_manifest.json` |
| 후보 기반 2AP 히트맵 | `02_auto_candidate_2ap/strongest_rssi_heatmap.png` |
| 2AP manifest | `02_auto_candidate_2ap/run_manifest.json` |
| 레이아웃 비교표 (JSON) | `layout_comparison_summary.json` |
| 레이아웃 비교표 (MD) | `layout_comparison_summary.md` |

## 재생성 (저장소 루트 기준)

```bash
cd service/ai-inference/app/rf
python finalize_presentation.py
```

matplotlib이 없으면 PNG는 생략되고 npy·manifest·비교 JSON/MD는 생성됩니다.

상위 안내: `app/rf/PRESENTATION_LOCKED.md`
