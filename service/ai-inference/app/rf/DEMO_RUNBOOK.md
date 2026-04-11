# RF baseline 데모 실행 절차 (발표·교수님 시연용)

**발표용 히트맵·비교표를 한 폴더에 고정하려면 `PRESENTATION_LOCKED.md`와 `finalize_presentation.py`를 먼저 참고하세요.**

아래는 **코드 없이** 재현할 수 있는 최소 절차입니다. 터미널에서 `service/ai-inference/app/rf` 기준으로 실행합니다.

```bash
cd service/ai-inference/app/rf
```

---

## 1) 실행 명령 3개 (이 순서)

### ① 회귀 테스트

```bash
python -m pytest tests/test_baseline_golden.py -v
```

**역할:** 고정된 미니 씬에서 baseline RSSI·커버리지 수치가 바뀌지 않았는지 확인합니다.

**기대:** `2 passed`. 실패 시 시뮬레이터나 의존 라이브러리(numpy)부터 점검합니다.

---

### ② E2E 파이프라인 (씬 → 후보 → top-K layout → 시뮬 → 저장)

```bash
python demo_rf_pipeline.py
```

**역할:** 같은 씬에 대해 휴리스틱 후보를 뽑고, 상위 K개로 `ApLayout`을 만든 뒤 baseline을 돌려 **히트맵·manifest·JSON 영속**까지 한 번에 생성합니다.

**생성되는 것 (기본 경로):**

| 구분 | 경로 |
|------|------|
| 시뮬 산출물 | `sample/output/pipeline_complex_demo/` — `run_manifest.json`, `strongest_rssi_heatmap.png`(matplotlib 있을 때), 각종 `.npy` |
| 영속(프로토타입) | `sample/output/pipeline_complex_demo/persistence/` — `rf_runs.json`, `ap_layouts.json`, `rf_maps.json` |

**해석:** `run_manifest.json`의 `metrics`에서 **mean/min RSSI**, `coverage_summary`(≥-67 / ≥-70 / &lt;-75 비율), `serving_ap_distribution`으로 “2AP가 공간을 나눠 서빙하는지”를 봅니다. 히트맵에서는 AP 위치와 방·벽·opening 오버레이를 함께 확인합니다.

---

### ③ 레이아웃 비교 (manual vs 후보 top1 vs 후보 top2)

```bash
python layout_comparator.py
```

**역할:** **동일 씬·동일 sim_config**에서 배치만 다르게 해 지표를 나란히 비교합니다. (기본은 복잡 씬 `rf_scene_input_complex.json`.)

**생성되는 것:**

| 구분 | 경로 |
|------|------|
| 비교 결과 | `sample/output/layout_comparison_summary.json` |
| 발표용 요약 문장 포함 | `sample/output/layout_comparison_summary.md` |

**해석:** 표·JSON의 **mean / min RSSI**, **coverage 비율**, **dead zone 비율**, **wall_loss mean**, **serving counts**를 보며 “단일 AP 대비 후보 기반 2AP가 개선되는지”를 숫자로 설명합니다. `interpretation_ko`(JSON·MD)는 같은 입력에 대한 자동 요약 문장입니다.

---

## 2) 현재 baseline의 가정

- **2D 단일 층**, 바닥 평면 위 격자에서 수신 전력만 계산합니다.
- **거리 기반 path loss**(로그 거리) + **벽과 교차 시 재질별 가산 감쇠**입니다.
- **개구부(opening) 선분**이 AP–수신점 직선과 겹치면, 그 벽 구간의 감쇠는 적용하지 않습니다.
- **여러 AP**일 때 수신점별 **strongest RSSI**만 사용합니다 (간섭·SINR 없음).
- 재질은 JSON의 **문자열 키** → `rf_materials`에 정의된 **고정 dB**로 매핑합니다.

---

## 3) 현재 baseline의 한계 (발표에서 밝히기)

- **실제 전파(반사·회절·3D)**를 모델링하지 않으며, **Sionna RT 등 정밀 레이 트레이싱과는 다릅니다.**
- **백엔드 scene graph → RF 자동 빌드 API**와는 연결되어 있지 않고, **합의된 RF JSON 파일**을 입력으로 둡니다.
- **DB의 material_id·운영 캘리브레이션**과는 직접 연동하지 않습니다.
- AP 후보는 **휴리스틱**이며 **전역 최적 배치 알고리즘**은 아닙니다.

---

## 참고: 발표용 산출물 한 폴더에 고정하기

슬라이드에 넣을 **단일 AP 히트맵 / 2AP 히트맵 / 비교표**를 한 디렉터리로 묶으려면:

```bash
python finalize_presentation.py
```

→ `sample/output/presentation_final/` (각 하위 폴더에 `run_manifest.json`·히트맵, 루트에 비교 JSON/MD)

위 3개 명령과 **별도**이며, “재현 가능한 최종 스냅샷”용입니다.
