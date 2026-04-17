# ai_api

`rf-service` 내 운영 FastAPI 앱입니다.  
U-Net/YOLO 추론과 Sionna API를 제공합니다. 이 문서는 실행/운영 상세 가이드입니다.

## Architecture (Current)

```text
app/
├─ api/routes              # endpoint
├─ presentation            # RequestDto / ResponseDto
├─ usecases                # usecase orchestration
├─ infrastructure          # runtime/sionna adapters
└─ main.py
```

실행 흐름:

- `api/routes` -> `usecases` -> `infrastructure` -> `packages/*`

## Run

아래 순서대로 따라오면 `ai_api` 기본 실행부터 RF(Sionna RT)까지 한 번에 세팅할 수 있습니다.

### 1) 기본 환경 준비 (필수)

```cmd
cd C:\capstone2\rf-service\apps\ai_api
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```

GPU 추론이 필요하면 추가 설치:

```cmd
python -m pip install -r requirements-gpu.txt
```

### 2) 가중치 파일 위치 (필수)

기본 `.env` 기준 권장 위치:

- U-Net checkpoint: `apps/trainer/src/models/unet/best_unet.pth`
- YOLO weights: `apps/trainer/src/models/yolo/best.pt`

예시:

```text
apps/trainer/src/models/
  unet/best_unet.pth
  yolo/best.pt
```

파일명이 다르면 `.env`에서 아래 두 값만 수정하면 됩니다.

- `UNET_CHECKPOINT_PATH`
- `YOLO_MODEL_PATH`

### 3) 기본 API 실행 (필수)

```cmd
cd C:\capstone2\rf-service\apps\ai_api
.\.venv\Scripts\activate
python -m uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

> `uvicorn ...` 대신 `python -m uvicorn ...`를 권장합니다.  
> 현재 활성화된 `.venv`의 Python으로 실행되어 인터프리터 혼선을 줄입니다.

### 4) RF(Sionna RT) 런타임 추가 설정 (선택)

`POST /internal/rf/run`을 실제 Sionna RT로 실행하려면 아래 추가 준비가 필요합니다.

#### 4-1) RF 전용 의존성 설치 (필수)

```cmd
cd C:\capstone2\rf-service\apps\ai_api
.\.venv\Scripts\activate
python -m pip install -r requirements-rf.txt
```

#### 4-2) LLVM 설치 및 환경변수 설정 (Windows, 필수)

Sionna RT는 `drjit/mitsuba` 경유로 `LLVM-C.dll`을 필요로 합니다.

1. LLVM 설치 (예: `C:\Program Files\LLVM\bin\LLVM-C.dll`)
2. 실행 셸에 맞게 환경변수 설정

CMD(현재 세션):

```cmd
set DRJIT_LIBLLVM_PATH=C:\Program Files\LLVM\bin\LLVM-C.dll
set PATH=C:\Program Files\LLVM\bin;%PATH%
```

PowerShell(현재 세션):

```powershell
$env:DRJIT_LIBLLVM_PATH="C:\Program Files\LLVM\bin\LLVM-C.dll"
$env:PATH="C:\Program Files\LLVM\bin;$env:PATH"
```

영구 설정(새 터미널부터 적용):

```cmd
setx DRJIT_LIBLLVM_PATH "C:\Program Files\LLVM\bin\LLVM-C.dll"
setx PATH "%PATH%;C:\Program Files\LLVM\bin"
```

프로젝트 로컬 설정으로는 `.env`에 아래 값을 추가해도 됩니다(앱 구동 시 로드).

```env
DRJIT_LIBLLVM_PATH=C:\Program Files\LLVM\bin\LLVM-C.dll
```

#### 4-3) 설치 검증 (필수)

```cmd
cd C:\capstone2\rf-service\apps\ai_api
.\.venv\Scripts\activate
python -c "import sys; print(sys.executable)"
python -c "import sionna.rt as rt; print('OK', rt.RadioMapSolver)"
```

위 명령이 성공하면 `sionna.rt` import 문제 없이 RF 엔드포인트를 사용할 수 있습니다.

### 5) RF 포함 실행

```cmd
cd C:\capstone2\rf-service\apps\ai_api
.\.venv\Scripts\activate
python -m uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

## Environment Variables

주요 항목:

- `UNET_CHECKPOINT_PATH`: U-Net 가중치 파일 경로
- `UNET_CONFIG_PATH`: U-Net 추론 설정 YAML 경로
- `YOLO_MODEL_PATH`: YOLO 가중치 파일 경로
- `YOLO_CONFIG_PATH`: YOLO 추론 설정 YAML 경로
- `YOLO_CONF_THRESHOLD`: YOLO confidence threshold
- `YOLO_DEVICE`: YOLO 디바이스 강제 지정(예: `cpu`, `cuda:0`)
- `DEFAULT_DEVICE`: 기본 디바이스(`auto|cpu|cuda`)
- `PRELOAD_MODELS`: 시작 시 모델 preload 여부(`true|false`)
- `SIONNA_ARTIFACT_IMAGE_URL_TEMPLATE`: Sionna 결과 `imageUrl` 템플릿 (`{sionna_run_id}` 사용)

### Common Startup Issues

- `No module named 'app'`
  - `apps/ai_api`에서 실행해야 함
  - 실행 커맨드는 `python -m uvicorn main:app ...`
- `No module named 'packages'`
  - `main.py` 엔트리포인트로 실행 중인지 확인 (`python -m uvicorn main:app`)
  - 실행 위치가 `apps/ai_api`인지 확인
- `Form data requires "python-multipart"`
  - `pip install -r requirements.txt` 재실행 (또는 `pip install python-multipart`)
- `No module named uvicorn`
  - `.venv` 활성화 후 `python -m pip install -r requirements.txt` 재실행
- `/internal/rf/run`에서 `ImportError: Sionna runtime is not available`
  - 서버가 `.venv` Python으로 뜨는지 확인 (`python -c "import sys; print(sys.executable)"`)
  - `DRJIT_LIBLLVM_PATH`가 올바른 `LLVM-C.dll`을 가리키는지 확인
  - `python -c "import sionna.rt as rt; print('OK', rt.RadioMapSolver)"` 검증 후 서버 실행
- Swagger에서 `422 Unprocessable Content` + `json_invalid`
  - Request body JSON 문법 확인 (키/문자열은 반드시 `"` 사용)

## API

- `GET /health`
- `POST /inference/unet`
- `POST /inference/yolo`
- `POST /internal/sionna/run`

문서:

- Swagger: `http://localhost:9000/docs`
- OpenAPI: `http://localhost:9000/openapi.json`

## Input/Output Notes

- `/inference/*`는 `multipart/form-data`:
  - `file_id`
  - `file` (`png|jpg|jpeg`)
- `/internal/sionna/run` 응답은 `imageUrl`(템플릿 기반 URL) 포함

## Backend Integration

`web-platform`(backend)에서 아래 값으로 호출:

```env
AI_SERVICE_URL=http://<ai-host>:9000
```
