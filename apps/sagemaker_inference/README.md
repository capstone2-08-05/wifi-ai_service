# sagemaker_inference

SageMaker Async Inference custom container.
도면 이미지를 S3에서 받아 U-Net (벽 세그멘테이션) + YOLO (객체 탐지) 추론을 수행하고, 결과 5종을 S3 `output_prefix` 에 PUT 한다.

**SceneDraft 변환은 이 컨테이너의 책임이 아니다.** 컨테이너는 raw outputs만 생성하고, 백엔드의 `fusion_service` 가 그것을 받아 변환한다. ([계약 문서](../../../docs/contracts/ai-inference/README.md) 참조)

## 디렉토리 구조

```
sagemaker_inference/
├── Dockerfile
├── requirements.txt
├── .dockerignore
├── app/
│   ├── main.py           # FastAPI /ping /invocations 엔드포인트
│   ├── handler.py        # 단일 요청 오케스트레이션
│   ├── contracts.py      # input.json 검증 + result/failure 빌더
│   ├── postprocess.py    # mask PNG / overlay PNG 인코딩
│   ├── s3_io.py          # S3 download/upload (boto3)
│   └── runtime.py        # 모델 preload + 디바이스 결정
├── schemas/              # docs/contracts/ai-inference/ 에서 vendored
├── scripts/
│   └── run_local_invocation.py
└── tests/
```

## 출력 5종 (output_prefix 하위)

| 파일 | 형식 | 용도 |
|---|---|---|
| `result.json` | JSON | 메타 + S3 URI 목록 + stage 시간 |
| `wall_mask.png` | PNG | U-Net binary mask (0/255) |
| `wall_prob_map.npy` | numpy float32 | U-Net 확률 맵 (H×W) |
| `detections.json` | JSON | YOLO bbox + class + score |
| `preview_overlay.png` | PNG | 시각화 (벽 heatmap + bbox) |
| `failure.json` | JSON | 실패 시. result.json 과 상호 배타적 |

## 로컬 개발

### 1) 단위 테스트 (Docker 없이)

```bash
cd rf-service
pip install -r apps/sagemaker_inference/requirements.txt
PYTHONPATH=apps/sagemaker_inference:. pytest apps/sagemaker_inference/tests -v
```

`contracts.py` 의 input 검증 / failure 빌더 등을 검증한다. 모델 로딩 / S3 호출은 포함하지 않는다.

### 2) 로컬 Docker 빌드

```bash
# 빌드 context = rf-service 디렉토리 (packages/, apps/ 가 같이 들어가야 함)
cd rf-service
docker build -f apps/sagemaker_inference/Dockerfile -t ai-inference:dev .
```

⚠️ 첫 빌드는 PyTorch base image (~6GB) + 의존성으로 10~15분 걸린다.

### 3) 로컬 실행

AWS credentials 와 실제 S3 bucket 이 필요하다. (또는 LocalStack 사용 — `AWS_S3_ENDPOINT_URL` 환경변수)

```bash
docker run --rm -p 8080:8080 \
    -e AWS_REGION=ap-northeast-2 \
    -v $HOME/.aws:/root/.aws:ro \
    ai-inference:dev
```

GPU 머신에서 테스트 시:

```bash
docker run --rm --gpus all -p 8080:8080 \
    -e AWS_REGION=ap-northeast-2 \
    -v $HOME/.aws:/root/.aws:ro \
    ai-inference:dev
```

### 4) Smoke test

```bash
# 다른 터미널에서 (테스트 이미지를 미리 S3에 업로드 해두어야 함)
python apps/sagemaker_inference/scripts/run_local_invocation.py \
    --source s3://my-bucket/projects/p1/source.png \
    --output-prefix s3://my-bucket/ai-jobs/local-test/output/
```

성공하면:
- `output_prefix/{result.json, wall_mask.png, wall_prob_map.npy, detections.json, preview_overlay.png}` 5개 생성
- 응답 본문 = result.json 내용

실패하면:
- `output_prefix/failure.json` 생성
- HTTP 4xx/5xx + 에러 JSON 응답

## SageMaker 규격 준수 확인

- ✅ `/ping` : 4초 이내 200 (모델 preload 완료 후)
- ✅ `/invocations` : POST 본문 처리, JSON 응답
- ✅ 포트 8080
- ✅ stderr/stdout 로그 (CloudWatch 자동 수집)

## 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `UNET_CHECKPOINT_PATH` | `/opt/ml/model/unet/best_unet.pth` | U-Net 가중치 (이미지에 굽혀 있음) |
| `UNET_CONFIG_PATH` | `/opt/ml/configs/unet_inference.yaml` | U-Net config |
| `YOLO_MODEL_PATH` | `/opt/ml/model/yolo/best.pt` | YOLO 가중치 |
| `YOLO_CONFIG_PATH` | `/opt/ml/configs/yolo_inference.yaml` | YOLO config |
| `DEFAULT_DEVICE` | `auto` | `cuda` / `cpu` / `auto` |
| `AWS_REGION` | — | S3 region |
| `AWS_S3_ENDPOINT_URL` | — | LocalStack/Minio 사용 시 |
| `CONTAINER_VERSION` | `ai-inference@0.1.0` | result.json runtime.container_version |

## 다음 단계

- **Issue D**: 이 이미지를 ECR 에 푸시하고 SageMaker Async Endpoint 로 배포 + scale-to-zero 설정
- **Issue E**: 백엔드 없이 E2E 검증 스크립트
