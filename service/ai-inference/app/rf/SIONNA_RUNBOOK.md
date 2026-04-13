# Sionna RT PoC 실행 런북 (Windows)

대상: `sionna_poc/sionna_rt_poc.py`, `compare_baseline_vs_sionna.py`

**역할:** Sionna는 **내부 precise 검증 엔진**이다. 사용자 서비스의 전면은 **2D floorplan**이며, 본 런북은 개발·검증용 (`docs/SERVICE_RF_ARCHITECTURE.md`).

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

## LLVM-C.dll · `DRJIT_LIBLLVM_PATH` (CPU / Dr.Jit)

**원인 정리:** `sionna-rt`·`mitsuba`·`drjit` wheel은 설치돼 있어도, **GPU(CUDA)를 쓰지 않고 CPU LLVM 백엔드**로 가면 Dr.Jit이 **`LLVM-C.dll`** 을 로드해야 한다. 이 DLL 경로를 못 찾으면 `import sionna.rt` 단계에서

`LLVM backend is inactive because the LLVM shared library ("LLVM-C.dll") could not be found`

같은 메시지로 막힌다. 이건 **pip 설치 실패가 아니라 런타임 공유 라이브러리 경로** 문제다. Sionna RT를 CPU에서 돌릴 때 LLVM이 필요하다는 점은 Sionna 쪽 안내와 맞는다.

### 1) Windows용 LLVM 바이너리 받기

- [LLVM 공식 릴리스](https://github.com/llvm/llvm-project/releases)에서 Windows용 아카이브(예: `LLVM-xx.x.x-win64.exe` 설치 프로그램 또는 `clang+llvm-*-win64-*.tar.xz`)를 받는다.
- 설치형이면 보통 **`...\LLVM\bin\LLVM-C.dll`** 이 생긴다. 압축 해제형이면 압축 안의 **`bin\LLVM-C.dll`** 을 찾는다.

### 2) 환경 변수 설정 (값은 **DLL 파일의 전체 경로**)

Dr.Jit 쪽 안내에 따라 **`DRJIT_LIBLLVM_PATH`** 에 **`LLVM-C.dll` 한 파일의 절대 경로**를 넣는다 (폴더만 넣지 말 것).

**현재 PowerShell 세션만:**

```powershell
$env:DRJIT_LIBLLVM_PATH = "C:\Path\To\LLVM\bin\LLVM-C.dll"
D:\venvs\wifi-ai-service\Scripts\python.exe -c "import sionna.rt; print('OK')"
```

**사용자 환경에 영구 반영 (시스템 속성 → 환경 변수, 또는):**

```powershell
[System.Environment]::SetEnvironmentVariable("DRJIT_LIBLLVM_PATH", "C:\Path\To\LLVM\bin\LLVM-C.dll", "User")
```

새 터미널을 연 뒤 다시 `import sionna.rt` 를 시도한다.

### 3) CUDA GPU만 쓰는 경우

NVIDIA 드라이버·CUDA가 맞고 Mitsuba가 **CUDA 변형**을 잡으면 LLVM 없이도 동작할 수 있다. 그런데도 CPU 폴백 시 같은 오류가 나면 위와 같이 LLVM 경로를 잡는다.

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
| `LLVM-C.dll` / `LLVM backend is inactive` | **설치 누락이 아님** → [위 절](#llvm-cdll-drjit_libllvm_path-cpu--drjit)대로 `LLVM-C.dll` 절대 경로를 `DRJIT_LIBLLVM_PATH`에 설정. 또는 CUDA 백엔드가 잡히도록 GPU 환경 정리 |
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
