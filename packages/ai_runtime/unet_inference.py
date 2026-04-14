from __future__ import annotations

from typing import Literal

import cv2
import numpy as np
import torch


def _letterbox_forward(
    rgb_patch: np.ndarray,
    target_size: int,
) -> tuple[np.ndarray, tuple[int, int, int, int, int, int]]:
    h, w = rgb_patch.shape[:2]
    if h == 0 or w == 0:
        raise ValueError("Invalid patch size (zero dimension).")
    scale = min(target_size / h, target_size / w)
    new_h = max(1, int(round(h * scale)))
    new_w = max(1, int(round(w * scale)))
    resized = cv2.resize(rgb_patch, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros((target_size, target_size, 3), dtype=resized.dtype)
    top = (target_size - new_h) // 2
    left = (target_size - new_w) // 2
    canvas[top : top + new_h, left : left + new_w] = resized
    meta = (h, w, top, left, new_h, new_w)
    return canvas, meta


def _letterbox_probs_inverse(
    probs: np.ndarray,
    meta: tuple[int, int, int, int, int, int],
) -> np.ndarray:
    h, w, top, left, new_h, new_w = meta
    crop = probs[top : top + new_h, left : left + new_w]
    return cv2.resize(crop, (w, h), interpolation=cv2.INTER_LINEAR)


def _patch_to_tensor(canvas: np.ndarray) -> torch.Tensor:
    t = canvas.astype(np.float32) / 255.0
    t = np.transpose(t, (2, 0, 1))
    return torch.from_numpy(t).unsqueeze(0)


@torch.no_grad()
def infer_sliding_window(
    rgb: np.ndarray,
    model: torch.nn.Module,
    device: torch.device,
    *,
    patch_size: int,
    image_size: int,
    stride: int,
    resize_mode: Literal["stretch", "letterbox"],
    threshold: float,
) -> tuple[np.ndarray, np.ndarray]:
    h, w = rgb.shape[:2]
    prob_sum = np.zeros((h, w), dtype=np.float32)
    weight = np.zeros((h, w), dtype=np.float32)

    if stride <= 0:
        raise ValueError("stride must be positive")
    if patch_size <= 0:
        raise ValueError("patch_size must be positive")

    y_positions = list(range(0, max(h, 1), stride))
    x_positions = list(range(0, max(w, 1), stride))
    if y_positions[-1] + patch_size < h:
        y_positions.append(max(0, h - patch_size))
    if x_positions[-1] + patch_size < w:
        x_positions.append(max(0, w - patch_size))
    y_positions = sorted(set(y_positions))
    x_positions = sorted(set(x_positions))

    model.eval()
    for y0 in y_positions:
        for x0 in x_positions:
            actual_h = min(patch_size, h - y0)
            actual_w = min(patch_size, w - x0)
            if actual_h <= 0 or actual_w <= 0:
                continue

            patch = np.zeros((patch_size, patch_size, 3), dtype=rgb.dtype)
            patch[0:actual_h, 0:actual_w] = rgb[y0 : y0 + actual_h, x0 : x0 + actual_w]

            if resize_mode == "letterbox":
                canvas, meta = _letterbox_forward(patch, image_size)
                tensor = _patch_to_tensor(canvas).to(device)
                logits = model(tensor)
                probs = torch.sigmoid(logits)[0, 0].cpu().numpy()
                probs_patch = _letterbox_probs_inverse(probs, meta)
            elif resize_mode == "stretch":
                canvas = cv2.resize(patch, (image_size, image_size), interpolation=cv2.INTER_LINEAR)
                tensor = _patch_to_tensor(canvas).to(device)
                logits = model(tensor)
                probs = torch.sigmoid(logits)[0, 0].cpu().numpy()
                probs_patch = cv2.resize(probs, (patch_size, patch_size), interpolation=cv2.INTER_LINEAR)
            else:
                raise ValueError(f"Unknown resize_mode: {resize_mode}")

            tile = probs_patch[0:actual_h, 0:actual_w]
            prob_sum[y0 : y0 + actual_h, x0 : x0 + actual_w] += tile
            weight[y0 : y0 + actual_h, x0 : x0 + actual_w] += 1.0

    w_safe = np.maximum(weight, 1e-6)
    prob_full = prob_sum / w_safe
    mask = (prob_full > threshold).astype(np.uint8) * 255
    return mask, prob_full


@torch.no_grad()
def infer_resize(
    rgb: np.ndarray,
    model: torch.nn.Module,
    device: torch.device,
    *,
    image_size: int,
    threshold: float,
) -> tuple[np.ndarray, np.ndarray]:
    orig_h, orig_w = rgb.shape[:2]
    resized = cv2.resize(rgb, (image_size, image_size), interpolation=cv2.INTER_LINEAR)
    tensor = _patch_to_tensor(resized).to(device)
    logits = model(tensor)
    probs = torch.sigmoid(logits)[0, 0].cpu().numpy()
    prob_full = cv2.resize(probs, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
    mask = (prob_full > threshold).astype(np.uint8) * 255
    return mask, prob_full
