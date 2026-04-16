# wifi-ai_service

U-Net / YOLO 추론과 RF preview 계산을 제공하는 AI 서비스 레포입니다.  
이 레포는 **운영 API**, **모델 학습/실험 코드**, **공용 패키지**를 분리해 관리합니다.

---

## Documents

처음 보는 분들은 아래 문서부터 확인해주세요.

- [운영 API 실행 가이드](./apps/ai_api/README.md)
- [모델 학습/실험 가이드](./apps/trainer/README.md)
- [네이밍 규칙](./docs/naming-conventions.md)

주요 코드 위치:

- [AI API 앱](./apps/ai_api)
- [공용 계약(Contracts)](./packages/contracts)
- [모델 런타임](./packages/ai_runtime)
- [RF/Sionna 런타임](./packages/ai_runtime)

---

## Architecture Overview

이 레포는 크게 **실행 가능한 앱(`apps/*`)** 과 **재사용 가능한 공용 패키지(`packages/*`)** 로 나뉩니다.

- `apps/ai_api`
  - 운영 FastAPI 앱입니다.
  - U-Net / YOLO 추론 API와 RF preview API를 제공합니다.
- `apps/trainer`
  - 모델 학습, 실험, CLI 추론 스크립트를 관리합니다.
- `packages/contracts`
  - 백엔드와 AI 서비스가 공유하는 요청/응답 계약(DTO, schema)입니다.
- `packages/ai_runtime`
  - 운영 API에서 재사용하는 U-Net / YOLO 런타임 모듈입니다.
- `packages/ai_runtime`
  - U-Net / YOLO / RF(Sionna RT) 런타임 모듈입니다.
- `docs`
  - 규약, 설계 문서, 개발 참고 문서를 관리합니다.

즉,

- **앱(`apps/*`)** 은 실행 가능한 진입점
- **패키지(`packages/*`)** 는 공용 로직
- **문서(`docs/*`)** 는 규약과 설계 설명

을 담당합니다.

---

## High-Level Architecture

```bash
flowchart LR
    Client[Backend / Client] --> API[apps/ai_api]

    API --> Routes[api/routes]
    Routes --> Usecases[usecases]
    Usecases --> Infra[infrastructure]

    Infra --> Contracts[packages/contracts]
    Infra --> AIRuntime[packages/ai_runtime]
    Infra --> AIRuntime[packages/ai_runtime]

    Trainer[apps/trainer] --> AIRuntime
```

### AI API Layered Structure

apps/ai_api/app 은 레이어드 구조를 따릅니다.

- api/routes
    - FastAPI endpoint 정의
- presentation
    - Request DTO / Response DTO
- usecases
    - 요청 처리 흐름 orchestration
- infrastructure
    - 모델 런타임, RF 코어 등 외부 모듈 호출
- domain
    - 도메인 엔티티

일반적인 요청 흐름은 아래와 같습니다.
```
api/routes -> usecases -> infrastructure -> packages/*
```
### Repository Structure
```
.
├─ apps/
│  ├─ ai_api/              # 운영 FastAPI 앱
│  └─ trainer/             # 모델 학습/실험 및 CLI 추론 코드
├─ packages/
│  ├─ contracts/           # 공용 요청/응답 계약(DTO, schema)
│  ├─ ai_runtime/          # U-Net / YOLO 런타임 모듈
│  └─ ai_runtime/          # U-Net / YOLO / RF(Sionna) 런타임
├─ docs/                   # 규약/설계 문서
└─ README.md
```

세부적으로는 다음과 같습니다.

- apps/ai_api
    - 운영 FastAPI 앱
    - 엔드포인트
- apps/trainer
    - 학습/실험 스크립트
    - CLI 추론 코드
- packages/contracts
    - 백엔드-서비스 공용 schema / DTO
- packages/ai_runtime
    - U-Net / YOLO / RF(Sionna RT) 로딩 및 추론 런타임
- docs
    - 개발 규약 및 참고 문서

### Quick Start

운영 API 실행은 apps/ai_api/README.md
 기준으로 진행하세요.
```
cd apps/ai_api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```
GPU 추론이 필요하면 추가로 설치합니다.
```
pip install -r requirements-gpu.txt
```
문서:

- 운영 API 실행 / 환경변수 / 트러블슈팅: apps/ai_api/README.md
- 모델 학습/실험: apps/trainer/README.md
- 네이밍 규칙: docs/naming-conventions.md

### Dependency Notes

운영 API 실행에 필요한 것은 기본적으로 아래 2개입니다.

- apps/ai_api/requirements.txt
- apps/ai_api/requirements-gpu.txt (GPU 사용 시)

아래 파일들은 용도가 다릅니다.

- apps/trainer/requirements*.txt
    - 모델 학습 / 실험용
    - 운영 API 필수 아님
### API Overview
**Inference APIs**
- POST /inference/unet
    - 입력 이미지에 대해 wall probability map 추론
- POST /inference/yolo
    - 입력 이미지에 대해 객체 탐지 수행

### 문서:

Swagger: http://localhost:9000/docs
OpenAPI: http://localhost:9000/openapi.json
Package Responsibilities
packages/contracts

백엔드와 AI 서비스가 공유하는 요청/응답 계약입니다.
서로 다른 앱에서 같은 schema를 사용하도록 source of truth 역할을 합니다.

### packages/ai_runtime

운영 API에서 재사용하는 모델 런타임입니다.

- U-Net 모델 로딩
- U-Net probability inference
- YOLO 모델 로딩
- YOLO inference 결과 생성

즉, 학습 코드 전체가 아니라 운영 API가 필요로 하는 추론 실행 로직만 분리한 패키지입니다.

- packages/ai_runtime

운영 API에서 재사용하는 모델 및 RF 런타임입니다.
