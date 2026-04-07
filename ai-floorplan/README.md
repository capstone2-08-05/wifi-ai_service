# ai-floorplan

U-Net 벽 분할 학습·추론 및 YOLO 관련 스크립트. 아래 명령은 **워킹 디렉터리를 `rf-service/ai-floorplan`으로 둔 것**을 기준으로 합니다.

## 환경

```powershell
cd c:\capstone2\rf-service\ai-floorplan
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## U-Net 학습

### 복붙용: 꼬임 없이 1개 loss만 새로 학습

`run_unet_losses.py`는 `train`/`infer` 서브커맨드를 같이 쓰므로, 아래처럼 `train --only`를 권장합니다.

```powershell
cd c:\capstone2\rf-service\ai-floorplan
python scripts/run_unet_losses.py train --only bce
```

학습이 정말 "새로" 시작되는지 확인하려면 콘솔 첫 줄의 `Config:`와 `save_dir:`를 확인하세요.

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
python -m src.training.train_unet
```

**loss별로 한 번에 학습**:

```powershell
python scripts/run_unet_losses.py train
```

일부만:

```powershell
python scripts/run_unet_losses.py train --only bce bce_dice
```

### 복붙용: loss별 단일 실행 명령

```powershell
cd c:\capstone2\rf-service\ai-floorplan
python scripts/run_unet_losses.py train --only bce
python scripts/run_unet_losses.py train --only bce_dice
python scripts/run_unet_losses.py train --only focal_dice
python scripts/run_unet_losses.py train --only tversky
python scripts/run_unet_losses.py train --only focal_tversky
```

체크포인트는 각 YAML의 `train.save_dir` 아래 `best_unet.pth`, `last_unet.pth`로 저장됩니다.

| 실험 tag | 설정 파일 | 저장 디렉터리 (기본) |
|----------|-----------|----------------------|
| `bce` | `configs/unet_bce.yaml` | `checkpoints/unet_bce` |
| `bce_dice` | `configs/unet_bce_dice.yaml` | `checkpoints/unet_bce_dice` |
| `focal_dice` | `configs/unet_focal_dice.yaml` | `checkpoints/unet_focal_dice` |
| `tversky` | `configs/unet_tversky.yaml` | `checkpoints/unet_tversky` |
| `focal_tversky` | `configs/unet_train.yaml` | `checkpoints/unet_focal_tversky` |

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
