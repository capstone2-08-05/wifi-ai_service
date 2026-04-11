# 발표용 baseline 결과 고정본 (1단계)

**목표:** 같은 코드·같은 입력 JSON으로 **언제 다시 실행해도 동일한 발표 세트**를 재현한다.  
(수치는 부동소수·라이브러리 버전에 아주 미세하게 달라질 수 있으나, **입력 파일 SHA는 `snapshot_meta.json`에 기록**한다.)

---

## 슬라이드에 쓸 산출물 3종 (경로 고정)

저장소 기준 루트에서 `service/ai-inference/app/rf/` 아래:

| # | 내용 | 파일 |
|---|------|------|
| 1 | **단일 AP** strongest RSSI 히트맵 | `sample/output/presentation_final/01_manual_single_ap/strongest_rssi_heatmap.png` |
| 2 | **자동 후보 2AP** 히트맵 | `sample/output/presentation_final/02_auto_candidate_2ap/strongest_rssi_heatmap.png` |
| 3 | **레이아웃 비교표** (Markdown 권장) | `sample/output/presentation_final/layout_comparison_summary.md` |

동일 수치·메타는 각각 `run_manifest.json`, `layout_comparison_summary.json`에 있다.

---

## 한 번에 고정 생성 (권장)

아래 **한 명령**으로 위 폴더 전체를 다시 쓴다 (씬·config·수동 layout은 복잡 씬 기준으로 고정).

```bash
cd service/ai-inference/app/rf
python -m pip install -r requirements-rf-lock.txt
python finalize_presentation.py
```

생성 후 **`sample/output/presentation_final/snapshot_meta.json`** 에 입력 JSON **SHA-256**과 출력 경로가 남는다.

---

## 검증용 실행 명령 3개 (회귀·데모·비교)

발표 직전 “시뮬레이터가 안 깨졌는지” 확인할 때만 순서대로:

```bash
cd service/ai-inference/app/rf
python -m pytest tests/test_baseline_golden.py -v
python demo_rf_pipeline.py
python layout_comparator.py
```

- `pytest`: 고정 미니 씬 **수치 회귀** (`2 passed` 기대).  
- `demo_rf_pipeline.py`: E2E 파이프라인·`sample/output/pipeline_complex_demo/` (발표 **스냅샷 폴더와 별개**).  
- `layout_comparator.py`: `sample/output/layout_comparison_summary.*` (기본 경로; **스냅샷은 `presentation_final/` 안이 최종본**).

자세한 설명은 **`DEMO_RUNBOOK.md`**.

---

## 가정·한계 (발표에서 한 장)

**`ASSUMPTIONS_AND_LIMITS.md`** 한 파일로 정리해 두었다. 슬라이드에 옮길 때는 그대로 발췌하면 된다.

---

## 입력이 바뀌면 안 되는 것 (재현성)

다음이 같아야 “같은 발표”다.

- `sample/rf_scene_input_complex.json`
- `sample/sim_config_complex.json`
- `sample/ap_layout_input_complex.json`
- `app/rf` 안의 시뮬레이터·후보 생성 코드 (회귀 테스트로 감시)

코드나 위 JSON을 바꾼 뒤에는 **`finalize_presentation.py`를 다시 실행**하고 `snapshot_meta.json`의 해시가 갱신됐는지 확인한다.
