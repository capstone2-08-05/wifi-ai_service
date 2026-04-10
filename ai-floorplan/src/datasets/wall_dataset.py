from __future__ import annotations

from pathlib import Path
from typing import Callable

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset


class FloorplanWallDataset(Dataset):
    def __init__(
        self,
        image_dir: str | Path,
        mask_dir: str | Path,
        image_size: int = 512,
        augment: bool = False,
    ):
        self.image_dir = Path(image_dir)
        self.mask_dir = Path(mask_dir)
        self.image_size = image_size
        self.augment = augment

        self.filenames = sorted([p.name for p in self.image_dir.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg"}])
        if not self.filenames:
            raise ValueError(f"No images found in {self.image_dir}")

        missing = [name for name in self.filenames if not (self.mask_dir / Path(name).with_suffix(".png").name).exists()]
        if missing:
            raise ValueError(f"Missing masks for {len(missing)} images. Example: {missing[:3]}")

    def __len__(self) -> int:
        return len(self.filenames)

    def _read_image(self, path: Path) -> np.ndarray:
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Failed to read image: {path}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return img

    def _read_mask(self, path: Path) -> np.ndarray:
        mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            raise ValueError(f"Failed to read mask: {path}")
        return mask

    def _augment(self, image: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if np.random.rand() < 0.5:
            image = np.fliplr(image).copy()
            mask = np.fliplr(mask).copy()

        if np.random.rand() < 0.2:
            image = np.flipud(image).copy()
            mask = np.flipud(mask).copy()

        return image, mask

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        name = self.filenames[idx]
        image_path = self.image_dir / name
        mask_path = self.mask_dir / Path(name).with_suffix(".png").name

        image = self._read_image(image_path)
        mask = self._read_mask(mask_path)

        if self.augment:
            image, mask = self._augment(image, mask)

        image = cv2.resize(image, (self.image_size, self.image_size), interpolation=cv2.INTER_LINEAR)
        mask = cv2.resize(mask, (self.image_size, self.image_size), interpolation=cv2.INTER_NEAREST)

        image = image.astype(np.float32) / 255.0
        mask = (mask > 127).astype(np.float32)

        image = np.transpose(image, (2, 0, 1))
        mask = np.expand_dims(mask, axis=0)

        return torch.from_numpy(image), torch.from_numpy(mask)