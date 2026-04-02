# rf-service

GPU 계산 전용 레포입니다.

## Directory

- `service/`: API 서비스 계층
- `service/ai-inference/`: U-Net/YOLO 추론 서비스
- `converters/`: scene -> RF scene 변환
- `runners/`: 시뮬레이션 실행 러너
- `sionna_rt/`: Sionna RT 스크립트/모듈
- `tests/`: smoke/integration 테스트
- `docker/`: 컨테이너 배포 설정

## Responsibilities

- scene 변환
- Sionna RT 실행
- heatmap/coverage 결과 생성 및 반환

## Contract

- 요청/응답 계약은 `web-platform/shared/api-contracts/`를 기준으로 맞춥니다.

python -m scripts.train_yolo ^
  --data data/yolo/dataset.yaml ^
  --model yolo11n.pt ^
  --imgsz 1024 ^
  --epochs 100 ^
  --batch 8 ^
  --device 0 ^
  --name cubicasa_4cls ^
  --save_period 10
