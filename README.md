# ai-service

GPU 기반 AI 학습 및 RF 계산 관련 서비스 레포입니다.

## Repository Structure

- `ai-floorplan/`: U-Net/YOLO 학습 및 추론 파이프라인
- `service/ai-inference/`: FastAPI 기반 AI 추론 서비스
- `converters/`: scene -> RF scene 변환 유틸
- `runners/`: 시뮬레이션 실행 러너
- `sionna_rt/`: Sionna RT 스크립트/모듈
- `tests/`: smoke/integration 테스트
- `docker/`: 컨테이너/배포 설정

## Start Here

- 모델 학습/실험 실행: `ai-floorplan/README.md`
- 추론 API 서비스 실행: `service/ai-inference/README.md`

## Responsibilities

- 도면/이미지 기반 AI 추론 수행
- scene 변환 및 RF 계산 파이프라인 실행
- heatmap/coverage 등 결과 생성 및 전달

## Contract

- 요청/응답 계약은 `web-platform/shared/api-contracts/` 기준으로 맞춥니다.
