from pathlib import Path
import cv2
import numpy as np

MASK_DIR = Path("data/unet/masks/train")
files = sorted(MASK_DIR.glob("*.png"))

for path in files[:50]:
    mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        print(f"읽기 실패: {path.name}")
        continue

    white_ratio = float((mask > 127).sum()) / mask.size
    print(f"{path.name}: white_ratio={white_ratio:.4f}")