from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import torch

from src.models.unet import UNet
from src.utils.common import ensure_dir, get_device, load_yaml


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--checkpoint", type=str, default="checkpoints/unet/best_unet.pth")
    parser.add_argument("--config", type=str, default="configs/unet_train.yaml")
    parser.add_argument("--out_dir", type=str, default="outputs/unet_infer")
    return parser.parse_args()


def preprocess(image_path: str, image_size: int):
    bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"Failed to read image: {image_path}")

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    orig_h, orig_w = rgb.shape[:2]

    resized = cv2.resize(rgb, (image_size, image_size), interpolation=cv2.INTER_LINEAR)
    tensor = resized.astype(np.float32) / 255.0
    tensor = np.transpose(tensor, (2, 0, 1))
    tensor = torch.from_numpy(tensor).unsqueeze(0)

    return rgb, tensor, (orig_w, orig_h)


@torch.no_grad()
def main():
    args = parse_args()
    cfg = load_yaml(args.config)
    device = get_device()

    model = UNet(
        in_channels=cfg["model"]["in_channels"],
        out_channels=cfg["model"]["out_channels"],
    ).to(device)

    ckpt = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    rgb, tensor, (orig_w, orig_h) = preprocess(args.image, cfg["data"]["image_size"])
    tensor = tensor.to(device)

    logits = model(tensor)
    probs = torch.sigmoid(logits)[0, 0].cpu().numpy()
    mask_small = (probs > cfg["infer"]["threshold"]).astype(np.uint8) * 255
    mask = cv2.resize(mask_small, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)

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


if __name__ == "__main__":
    main()