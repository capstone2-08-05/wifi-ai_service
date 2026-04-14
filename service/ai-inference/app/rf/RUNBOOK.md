# RF 실행·발표·Sionna (통합 런북)

**서비스 메시지:** UI는 **2D floorplan**(heatmap·AP·재질·창문·가구). **Baseline** = 빠른 preview, **Sionna RT** = 내부 precise 검증(제품 전면의 3D 뷰 아님). 상세 역할: `docs/SCENE_GRAPH_ADAPTER_MAPPING.md` 서문.

터미널 기준 경로: `service/ai-inference/app/rf`

```bash
cd service/ai-inference/app/rf
```

---

## A) 발표용 산출물 한 폴더 고정

같은 씬·config에서 AP 배치만 바꾼 **히트맵·비교표**를 `sample/output/presentation_final/`에 모으려면:

```bash
python -m pip install -r requirements-rf-lock.txt
python finalize_presentation.py
```

산출: `01_manual_single_ap/`, `02_auto_candidate_2ap/`, `layout_comparison_summary.*`, `snapshot_meta.json`. 상세 표는 `sample/output/presentation_final/README.md`.

---

## B) 데모 파이프라인 (회귀 → E2E → 레이아웃 비교)

### ① 회귀 테스트

```bash
python -m pytest tests/test_baseline_golden.py -v
```

기대: `2 passed`.

### ② E2E (`demo_rf_pipeline.py`)

```bash
python demo_rf_pipeline.py
```

기본 출력: `sample/output/pipeline_complex_demo/` (manifest, heatmap, npy, persistence).

### ③ 레이아웃 비교

```bash
python layout_comparator.py
```

출력: `sample/output/layout_comparison_summary.json`, `.md`.

### 가정·한계 (발표 시 밝히기)

- 2D 단일 층, strongest RSSI, 간섭·SINR 없음.
- 정밀 전파는 Sionna 등과 다름; 백엔드 scene graph 자동 API와 미연동(합의 RF JSON 입력).
- AP 후보는 휴리스틱.

---

## C) Sionna RT PoC (내부 검증)

대상: `sionna_poc/sionna_rt_poc.py`, `compare_baseline_vs_sionna.py`

### venv + 설치

```powershell
D:\venvs\wifi-ai-service\Scripts\python.exe -m pip install -r requirements-sionna-poc.txt
cd <repo>\service\ai-inference\app\rf
D:\venvs\wifi-ai-service\Scripts\python.exe sionna_poc\sionna_rt_poc.py --out-json sample\output\sionna_poc_report.json
D:\venvs\wifi-ai-service\Scripts\python.exe compare_baseline_vs_sionna.py
```

`pip`는 **해당 venv의 `python -m pip`** 로 설치할 것.

### LLVM-C.dll (`DRJIT_LIBLLVM_PATH`)

CPU LLVM 백엔드 사용 시 `LLVM-C.dll` 절대 경로를 환경 변수 `DRJIT_LIBLLVM_PATH`에 설정. (폴더가 아니라 **파일** 경로.)

### 생성물

| 파일 | 설명 |
|------|------|
| `sample/output/baseline_vs_sionna_summary.json` / `.md` | 통합 비교 |
| `sample/output/sionna_poc_report.json` | PoC 단독 시 `--out-json` |

실패 시: `No module named sionna` → 의존성 설치; LLVM 메시지 → 위 환경 변수. 상세 규칙: `docs/RF_MATERIAL_AND_OPENING_RULES.md`.
