# ai-floorplan

U-Net 벽 분할 학습·추론 및 YOLO 관련 스크립트. 아래 명령은 **워킹 디렉터리를 `ai-service/ai-floorplan`으로 둔 것**을 기준으로 합니다.

## 환경

```powershell
cd c:\capstone2\rf-service\ai-floorplan
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## U-Net 학습

### 복붙용: 1개 loss 단일 학습

한 번에 여러 loss를 돌리는 방식 대신, 아래처럼 `train_unet --config` 단일 실행을 권장합니다.

```powershell
cd c:\capstone2\rf-service\ai-floorplan
python -m src.training.train_unet --config configs/unet_bce.yaml
```

학습이 정말 "새로" 시작되는지 확인하려면 콘솔 첫 줄의 `Config:`와 `save_dir:`를 확인하세요.

중단된 학습 이어서 재개:

```powershell
cd c:\capstone2\rf-service\ai-floorplan
python -m src.training.train_unet --config configs/unet_bce.yaml --resume checkpoints/unet_bce/last_unet.pth
```

단일 실험(설정 파일 지정):

```powershell
python -m src.training.train_unet --config configs/unet_bce.yaml
python -m src.training.train_unet --config configs/unet_bce_dice.yaml
python -m src.training.train_unet --config configs/unet_focal_dice.yaml
python -m src.training.train_unet --config configs/unet_tversky.yaml
python -m src.training.train_unet --config configs/unet_train.yaml
```

기본 설정으로 돌리려면(`configs/unet_train.yaml`, loss: `focal_tversky`):

```powershell
python -m src.training.train_unet --config configs/unet_train.yaml
```

### 복붙용: loss별 단일 실행 명령

```powershell
cd c:\capstone2\rf-service\ai-floorplan
python -m src.training.train_unet --config configs/unet_bce.yaml
python -m src.training.train_unet --config configs/unet_bce_dice.yaml
python -m src.training.train_unet --config configs/unet_focal_dice.yaml
python -m src.training.train_unet --config configs/unet_tversky.yaml
python -m src.training.train_unet --config configs/unet_train.yaml
```

체크포인트는 각 YAML의 `train.save_dir` 아래 `best_unet.pth`, `last_unet.pth`로 저장됩니다.

| 실험 tag | 설정 파일 | 저장 디렉터리 (기본) |
|----------|-----------|----------------------|
| `bce` | `configs/unet_bce.yaml` | `checkpoints/unet_bce` |
| `bce_dice` | `configs/unet_bce_dice.yaml` | `checkpoints/unet_bce_dice` |
| `focal_dice` | `configs/unet_focal_dice.yaml` | `checkpoints/unet_focal_dice` |
| `tversky` | `configs/unet_tversky.yaml` | `checkpoints/unet_tversky` |
| `focal_tversky` | `configs/unet_train.yaml` | `checkpoints/unet_focal_tversky` |

### YAML에 무엇을 명시해야 하나?

`train_unet.py`는 CLI 기본값으로 덮어쓰기하지 않고, YAML 값을 기준으로 동작합니다.

필수:
- `seed` (랜덤 시드 고정값)
- `data.train_image_dir` (학습 이미지 폴더)
- `data.train_mask_dir` (학습 마스크 폴더)
- `data.val_image_dir` (검증 이미지 폴더)
- `data.val_mask_dir` (검증 마스크 폴더)
- `data.image_size` (최종 입력 해상도, 정사각형 한 변)
- `train.batch_size` (배치 크기)
- `train.epochs` (총 학습 epoch 수)
- `train.lr` (학습률)
- `train.num_workers` (DataLoader 워커 수)
- `train.save_dir` (체크포인트/로그 저장 경로)
- `train.amp` (mixed precision 사용 여부, `true/false`)
- `model.in_channels` (입력 채널 수, 일반 RGB는 3)
- `model.out_channels` (출력 채널 수, 벽 이진 분할은 보통 1)
- `loss.name` (손실 함수 이름: `bce`, `bce_dice`, `focal_dice`, `tversky`, `focal_tversky`)

권장(명시 추천):
- `data.resize_mode` (리사이즈 방식: `letterbox` 또는 `stretch`, 미명시 시 기본값: `letterbox`)
- `data.train_patch_size` (학습 시 패치 크기, 미명시 시 기본값: `null` = 패치 크롭 미사용)
- `data.val_patch_size` (검증 시 패치 크기, 미명시 시 기본값: `null` = 패치 크롭 미사용)
- `data.wall_focus_prob` (벽이 있는 패치를 우선 샘플링할 확률, 미명시 시 기본값: `0.7`)
- `data.min_wall_ratio` (벽 중심 샘플링으로 인정할 최소 벽 비율, 미명시 시 기본값: `0.01`)
- `data.patch_max_tries` (조건 맞는 패치 찾기 재시도 횟수, 미명시 시 기본값: `10`)
- `augment.flip_h_prob` (좌우 뒤집기 확률, 미명시 시 기본값: `0.5`)
- `augment.flip_v_prob` (상하 뒤집기 확률, 미명시 시 기본값: `0.2`, 증강 미사용이면 `augment` 섹션 생략 가능)
- `infer.threshold` (시그모이드 출력 이진화 임계값, 미명시 시 각 추론 스크립트 기본값 사용)
- `infer.sliding_window` (슬라이딩 윈도우 추론 사용 여부, 미명시 시 각 추론 스크립트 기본값 사용)
- `infer.patch_size` (슬라이딩 윈도우 패치 크기, 미명시 시 각 추론 스크립트 기본값 사용)
- `infer.stride` (슬라이딩 윈도우 이동 간격, 미명시 시 각 추론 스크립트 기본값 사용)

참고:
- 과거 형식 `train.loss_name`도 호환은 되지만, 새 설정은 `loss.name` 사용을 권장합니다.
- 증강 on/off 판단 순서: `augment.enabled` -> `data.augment` -> `augment` 섹션 존재 여부.
- 학습 재개는 YAML이 아니라 CLI 인자로 지정합니다.  
  예: `python -m src.training.train_unet --config configs/unet_bce.yaml --resume checkpoints/unet_bce/last_unet.pth`

## U-Net 추론

단일 이미지(해당 실험과 같은 `--config`를 맞추는 것을 권장):

```powershell
python -m src.inference.infer_unet --image data/unet/test/test.jpg --checkpoint checkpoints/unet_bce/best_unet.pth --config configs/unet_bce.yaml --out_dir outputs/unet_infer
```

**loss별로 일괄 추론**(체크포인트가 없는 tag는 건너뜀):

```powershell
python scripts/run_unet_losses.py infer --image data/unet/test/test.jpg
```

출력: `outputs/unet_infer/<tag>/`.

`last` 가중치를 쓰려면:

```powershell
python scripts/run_unet_losses.py infer --image data/unet/test/test.jpg --checkpoint last_unet.pth
```

일부 실험만:

```powershell
python scripts/run_unet_losses.py infer --image data/unet/test/test.jpg --only focal_tversky
```

추론 옵션(슬라이딩 윈도우, stride 등)은 각 설정 파일의 `infer` 섹션과 `data`(패치·리사이즈)를 참고하세요. CLI로 덮어쓰기: `infer_unet.py --help`.

## Val 평가와 Sliding Window

- 현재 학습 중 `val_dice`/`val_iou`는 `train_unet.py`의 내부 검증 루프(배치 단위 forward)로 계산됩니다.
- `sliding window`는 `infer_unet.py` 추론 경로에서만 사용됩니다.
- 최종 운영 추론이 `sliding window`라면, **최종 비교/리포트용 평가는 sliding window 기반으로 별도 계산**하는 것을 권장합니다.
- 단, 학습 중 빠른 피드백용 `val_dice`는 현재 방식 그대로 두는 편이 일반적입니다(속도 이점).

## 데이터 준비 (CubiCasa 벽 마스크)

예시:

```powershell
python scripts/prepare_cubicasa_walls.py --help
```

원시 CubiCasa 정리 후 `data/unet/images/{train,val}`, `data/unet/masks/{train,val}` 구조에 맞춥니다.
