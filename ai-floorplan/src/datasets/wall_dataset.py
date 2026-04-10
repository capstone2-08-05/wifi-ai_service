from __future__ import annotations

from pathlib import Path
from typing import Literal

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
        resize_mode: Literal["stretch", "letterbox"] = "letterbox",
        patch_size: int | None = None,
        wall_focus_prob: float = 0.7,
        min_wall_ratio: float = 0.01,
        patch_max_tries: int = 10,
        flip_h_prob: float = 0.5,
        flip_v_prob: float = 0.2,
    ):
        self.image_dir = Path(image_dir)
        self.mask_dir = Path(mask_dir)
        self.image_size = image_size
        self.augment = augment
        self.resize_mode = resize_mode
        self.patch_size = patch_size
        self.wall_focus_prob = wall_focus_prob
        self.min_wall_ratio = min_wall_ratio
        self.patch_max_tries = patch_max_tries
        self.flip_h_prob = float(flip_h_prob)
        self.flip_v_prob = float(flip_v_prob)

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
        if np.random.rand() < self.flip_h_prob:
            image = np.fliplr(image).copy()
            mask = np.fliplr(mask).copy()

        if np.random.rand() < self.flip_v_prob:
            image = np.flipud(image).copy()
            mask = np.flipud(mask).copy()

        return image, mask

    def _resize_with_aspect_pad(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        target_size: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        h, w = image.shape[:2]
        if h == 0 or w == 0:
            raise ValueError("Invalid image size (zero dimension).")

        scale = min(target_size / h, target_size / w)
        new_h = max(1, int(round(h * scale)))
        new_w = max(1, int(round(w * scale)))

        resized_image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        resized_mask = cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)

        canvas_image = np.zeros((target_size, target_size, 3), dtype=resized_image.dtype)
        canvas_mask = np.zeros((target_size, target_size), dtype=resized_mask.dtype)

        top = (target_size - new_h) // 2
        left = (target_size - new_w) // 2
        canvas_image[top : top + new_h, left : left + new_w] = resized_image
        canvas_mask[top : top + new_h, left : left + new_w] = resized_mask
        return canvas_image, canvas_mask

    def _sample_patch(self, image: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.patch_size is None:
            return image, mask

        patch_size = self.patch_size
        h, w = image.shape[:2]
        if h < patch_size or w < patch_size:
            pad_h = max(0, patch_size - h)
            pad_w = max(0, patch_size - w)
            top = pad_h // 2
            bottom = pad_h - top
            left = pad_w // 2
            right = pad_w - left
            image = cv2.copyMakeBorder(image, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(0, 0, 0))
            mask = cv2.copyMakeBorder(mask, top, bottom, left, right, cv2.BORDER_CONSTANT, value=0)
            h, w = image.shape[:2]

        wall_focus = np.random.rand() < self.wall_focus_prob
        best_patch = None
        best_ratio = -1.0

        for _ in range(self.patch_max_tries):
            y0 = np.random.randint(0, h - patch_size + 1)
            x0 = np.random.randint(0, w - patch_size + 1)
            patch_mask = mask[y0 : y0 + patch_size, x0 : x0 + patch_size]
            wall_ratio = float((patch_mask > 127).mean())

            if not wall_focus:
                best_patch = (y0, x0)
                break

            if wall_ratio >= self.min_wall_ratio:
                best_patch = (y0, x0)
                break

            if wall_ratio > best_ratio:
                best_ratio = wall_ratio
                best_patch = (y0, x0)

        if best_patch is None:
            y0, x0 = 0, 0
        else:
            y0, x0 = best_patch

        image_patch = image[y0 : y0 + patch_size, x0 : x0 + patch_size]
        mask_patch = mask[y0 : y0 + patch_size, x0 : x0 + patch_size]
        return image_patch, mask_patch

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        name = self.filenames[idx]
        image_path = self.image_dir / name
        mask_path = self.mask_dir / Path(name).with_suffix(".png").name

        image = self._read_image(image_path)
        mask = self._read_mask(mask_path)

        if self.augment:
            image, mask = self._augment(image, mask)

        image, mask = self._sample_patch(image, mask)

        if self.resize_mode == "stretch":
            image = cv2.resize(image, (self.image_size, self.image_size), interpolation=cv2.INTER_LINEAR)
            mask = cv2.resize(mask, (self.image_size, self.image_size), interpolation=cv2.INTER_NEAREST)
        elif self.resize_mode == "letterbox":
            image, mask = self._resize_with_aspect_pad(image, mask, target_size=self.image_size)
        else:
            raise ValueError(f"Unknown resize_mode: {self.resize_mode}")

        image = image.astype(np.float32) / 255.0
        mask = (mask > 127).astype(np.float32)

        image = np.transpose(image, (2, 0, 1))
        mask = np.expand_dims(mask, axis=0)

        return torch.from_numpy(image), torch.from_numpy(mask)