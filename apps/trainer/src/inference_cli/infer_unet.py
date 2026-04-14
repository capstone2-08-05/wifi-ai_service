from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
import torch
import yaml

from packages.ai_runtime.unet_model import UNet


def ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--checkpoint", type=str, default="checkpoints/unet/best_unet.pth")
    parser.add_argument("--config", type=str, default="configs/unet_train.yaml")
    parser.add_argument("--out_dir", type=str, default="outputs/unet_infer")
    parser.add_argument(
        "--sliding",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Sliding-window patch inference (default: from config infer.sliding_window)",
    )
    parser.add_argument("--patch_size", type=int, default=None, help="Override infer.patch_size")
    parser.add_argument("--stride", type=int, default=None, help="Override infer.stride")
    return parser.parse_args()


def _letterbox_forward(
    rgb_patch: np.ndarray,
    target_size: int,
) -> tuple[np.ndarray, tuple[int, int, int, int, int, int]]:
    """Match training letterbox: fit inside target_size×target_size, pad with zeros."""
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
    """
    Tile the image with patch_size windows (zero-pad at edges), run U-Net per tile,
    map logits back to patch resolution, stitch with overlap averaging.
    Returns (binary_mask_uint8_HxW, prob_float32_HxW).
    """
    H, W = rgb.shape[:2]
    prob_sum = np.zeros((H, W), dtype=np.float32)
    weight = np.zeros((H, W), dtype=np.float32)

    if stride <= 0:
        raise ValueError("stride must be positive")
    if patch_size <= 0:
        raise ValueError("patch_size must be positive")

    y_positions = list(range(0, max(H, 1), stride))
    x_positions = list(range(0, max(W, 1), stride))
    if y_positions[-1] + patch_size < H:
        y_positions.append(max(0, H - patch_size))
    if x_positions[-1] + patch_size < W:
        x_positions.append(max(0, W - patch_size))
    y_positions = sorted(set(y_positions))
    x_positions = sorted(set(x_positions))

    model.eval()
    for y0 in y_positions:
        for x0 in x_positions:
            actual_h = min(patch_size, H - y0)
            actual_w = min(patch_size, W - x0)
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
    """Legacy: whole image stretched to image_size, then mask resized back."""
    orig_h, orig_w = rgb.shape[:2]
    resized = cv2.resize(rgb, (image_size, image_size), interpolation=cv2.INTER_LINEAR)
    tensor = _patch_to_tensor(resized).to(device)
    logits = model(tensor)
    probs = torch.sigmoid(logits)[0, 0].cpu().numpy()
    prob_small = probs
    prob_full = cv2.resize(prob_small, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
    mask = (prob_full > threshold).astype(np.uint8) * 255
    return mask, prob_full


def main():
    args = parse_args()
    cfg = load_yaml(args.config)
    device = get_device()

    data_cfg = cfg["data"]
    infer_cfg = cfg.get("infer", {})
    image_size = int(data_cfg["image_size"])
    threshold = float(infer_cfg.get("threshold", 0.5))
    resize_mode = str(data_cfg.get("resize_mode", "letterbox"))
    if resize_mode not in ("stretch", "letterbox"):
        raise ValueError(f"Unsupported resize_mode for inference: {resize_mode}")

    patch_default = infer_cfg.get("patch_size")
    if patch_default is None:
        patch_default = data_cfg.get("train_patch_size") or image_size
    patch_size = int(args.patch_size if args.patch_size is not None else patch_default)

    stride_default = infer_cfg.get("stride")
    if stride_default is None:
        stride_default = max(1, patch_size // 2)
    stride = int(args.stride if args.stride is not None else stride_default)

    use_sliding = infer_cfg.get("sliding_window", True)
    if args.sliding is not None:
        use_sliding = args.sliding

    model = UNet(
        in_channels=cfg["model"]["in_channels"],
        out_channels=cfg["model"]["out_channels"],
    ).to(device)

    ckpt = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    bgr = cv2.imread(args.image, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"Failed to read image: {args.image}")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    if use_sliding:
        mask, _prob = infer_sliding_window(
            rgb,
            model,
            device,
            patch_size=patch_size,
            image_size=image_size,
            stride=stride,
            resize_mode=resize_mode,  # type: ignore[arg-type]
            threshold=threshold,
        )
    else:
        mask, _prob = infer_resize(
            rgb,
            model,
            device,
            image_size=image_size,
            threshold=threshold,
        )

    overlay = rgb.copy()
    overlay[mask > 0] = (overlay[mask > 0] * 0.5 + np.array([255, 0, 0]) * 0.5).astype(np.uint8)

    out_dir = ensure_dir(args.out_dir)
    stem = Path(args.image).stem

    mask_path = out_dir / f"{stem}_wall_mask.png"
    overlay_path = out_dir / f"{stem}_wall_overlay.png"

    cv2.imwrite(str(mask_path), mask)
    cv2.imwrite(str(overlay_path), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))

    print(f"Saved mask: {mask_path}")
    print(f"Saved overlay: {overlay_path}")
    if use_sliding:
        print(f"(sliding window patch_size={patch_size} stride={stride} resize_mode={resize_mode})")


if __name__ == "__main__":
    main()
