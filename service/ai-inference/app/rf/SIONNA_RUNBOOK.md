# Sionna RT PoC 실행 런북 (Windows)

대상: `sionna_poc/sionna_rt_poc.py`, `compare_baseline_vs_sionna.py`

## 사전 조건

- Python 3.11+ 권장 (레포는 3.13 예시 있음)
- **가상환경은 C:가 아닌 D: 등 여유 디스크에** 두는 것을 권장
- 패키지: `app/rf/requirements-sionna-poc.txt`

## 실행 명령 1세트 (venv)

```powershell
D:\venvs\wifi-ai-service\Scripts\python.exe -m pip install -r C:\Users\soohyun\Desktop\wifi-ai_service\service\ai-inference\app\rf\requirements-sionna-poc.txt

cd C:\Users\soohyun\Desktop\wifi-ai_service\service\ai-inference\app\rf

D:\venvs\wifi-ai-service\Scripts\python.exe sionna_poc\sionna_rt_poc.py --out-json sample\output\sionna_poc_report.json

D:\venvs\wifi-ai-service\Scripts\python.exe compare_baseline_vs_sionna.py
```

`pip`는 반드시 **`...\Scripts\python.exe -m pip`** 로 venv에 설치한다 (전역 Python에 깔리는 실수 방지).

## 성공 시 생성물

| 파일 | 내용 |
|------|------|
| `sample/output/sionna_poc_report.json` | `sionna_rt_poc.py --out-json` 로 저장 시 baseline 요약 + Sionna RSS 요약 |
| `sample/output/baseline_vs_sionna_summary.json` | `compare_baseline_vs_sionna.py` 통합 리포트 |
| `sample/output/baseline_vs_sionna_summary.md` | 발표용 요약 표 + 한 줄 해석 |

### `sionna_poc_report.json` 예시 형식

```json
{
  "purpose": "wifi-ai RF 입력 구조가 Sionna RT RadioMap으로 이어지는지 최소 검증",
  "layout": { "room_m": [4.0, 4.0], "ap_position_m": [2.0, 2.0, 2.5], "materials_itu": { "...": "..." } },
  "baseline_reference": { "model": "baseline_rf_simulator", "rssi_dbm": { "min": "...", "max": "...", "mean": "..." } },
  "sionna_radiomap": { "model": "sionna_rt_radiomap", "rss_dbm": { "...": "..." }, "solver": { "...": "..." } }
}
```

## 실패 포인트 체크리스트

| 증상 | 조치 |
|------|------|
| `No module named 'sionna'` | `requirements-sionna-poc.txt` 설치, venv 활성화 여부 확인 |
| `LLVM-C.dll` / `LLVM backend is inactive` | LLVM 설치 후 `DRJIT_LIBLLVM_PATH`에 **DLL 파일 전체 경로** 지정, 또는 NVIDIA **CUDA** 환경 구축 |
| `cuda` 관련 로드 실패 | GPU 드라이버·CUDA Toolkit 정합성 확인 |
| `pip`가 `python313\Lib\site-packages`에 설치 | `python -m pip`가 **venv의 python**인지 확인 (`where python`) |
| C: 디스크 부족 | pip 캐시를 D:로 (`pip config set global.cache-dir D:\pip-cache`), venv를 D:에 생성 |

## 성공 판정 (최소)

1. `import sionna.rt` 가 예외 없이 된다.
2. `sionna_rt_poc.py` 가 종료 코드 0으로 끝나고 JSON에 `sionna_radiomap` 숫자가 채워진다.
3. `compare_baseline_vs_sionna.py` 결과에서 `sionna.status == "ok"` (또는 환경 제약 시 baseline만이라도 `baseline.status == "ok"`).

## 참고

- Baseline golden은 **벽 없음**; Sionna PoC는 **바닥+벽 메시** — 수치 1:1 비교는 하지 않는다.
- 상세: `docs/RF_MATERIAL_AND_OPENING_RULES.md`, `ASSUMPTIONS_AND_LIMITS.md`
