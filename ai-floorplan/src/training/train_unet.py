from __future__ import annotations

import argparse
from pathlib import Path

import torch
from torch.cuda.amp import GradScaler, autocast
from torch.utils.data import DataLoader
from tqdm import tqdm

from src.datasets.wall_dataset import FloorplanWallDataset
from src.models.unet import UNet
from src.utils.common import ensure_dir, get_device, load_yaml, set_seed
from src.utils.losses import build_loss
from src.utils.metrics import dice_score_from_logits, iou_score_from_logits


def train_one_epoch(model, loader, optimizer, criterion, device, scaler, use_amp: bool):
    model.train()
    total_loss = 0.0

    for images, masks in tqdm(loader, desc="train", leave=False):
        images = images.to(device)
        masks = masks.to(device)

        optimizer.zero_grad(set_to_none=True)

        with autocast(enabled=use_amp):
            logits = model(images)
            loss = criterion(logits, masks)

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        total_loss += loss.item()

    return total_loss / max(len(loader), 1)


@torch.no_grad()
def validate(model, loader, criterion, device):
    model.eval()
    total_loss = 0.0
    total_dice = 0.0
    total_iou = 0.0

    for images, masks in tqdm(loader, desc="val", leave=False):
        images = images.to(device)
        masks = masks.to(device)

        logits = model(images)
        loss = criterion(logits, masks)

        total_loss += loss.item()
        total_dice += dice_score_from_logits(logits, masks).item()
        total_iou += iou_score_from_logits(logits, masks).item()

    n = max(len(loader), 1)
    return {
        "loss": total_loss / n,
        "dice": total_dice / n,
        "iou": total_iou / n,
    }


def parse_args():
    p = argparse.ArgumentParser(description="Train U-Net wall segmentation.")
    p.add_argument(
        "--config",
        type=str,
        default="configs/unet_train.yaml",
        help="Path to YAML config (default: configs/unet_train.yaml)",
    )
    return p.parse_args()


def main():
    args = parse_args()
    cfg_path = Path(args.config)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Config not found: {cfg_path.resolve()}")
    cfg = load_yaml(str(cfg_path))
    set_seed(cfg["seed"])
    device = get_device()

    aug_cfg = cfg.get("augment") or {}
    train_ds = FloorplanWallDataset(
        image_dir=cfg["data"]["train_image_dir"],
        mask_dir=cfg["data"]["train_mask_dir"],
        image_size=cfg["data"]["image_size"],
        augment=True,
        resize_mode=cfg["data"].get("resize_mode", "letterbox"),
        patch_size=cfg["data"].get("train_patch_size"),
        wall_focus_prob=cfg["data"].get("wall_focus_prob", 0.7),
        min_wall_ratio=cfg["data"].get("min_wall_ratio", 0.01),
        patch_max_tries=cfg["data"].get("patch_max_tries", 10),
        flip_h_prob=float(aug_cfg.get("flip_h_prob", 0.5)),
        flip_v_prob=float(aug_cfg.get("flip_v_prob", 0.2)),
    )
    val_ds = FloorplanWallDataset(
        image_dir=cfg["data"]["val_image_dir"],
        mask_dir=cfg["data"]["val_mask_dir"],
        image_size=cfg["data"]["image_size"],
        augment=False,
        resize_mode=cfg["data"].get("resize_mode", "letterbox"),
        patch_size=cfg["data"].get("val_patch_size"),
        wall_focus_prob=cfg["data"].get("wall_focus_prob", 0.7),
        min_wall_ratio=cfg["data"].get("min_wall_ratio", 0.01),
        patch_max_tries=cfg["data"].get("patch_max_tries", 10),
    )

    train_loader = DataLoader(
        train_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=True,
        num_workers=cfg["train"]["num_workers"],
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=False,
        num_workers=cfg["train"]["num_workers"],
        pin_memory=True,
    )

    model = UNet(
        in_channels=cfg["model"]["in_channels"],
        out_channels=cfg["model"]["out_channels"],
    ).to(device)

    criterion = build_loss(cfg.get("loss", {"name": "bce"}))
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["train"]["lr"])
    scaler = GradScaler(enabled=cfg["train"]["amp"])

    save_dir = ensure_dir(cfg["train"]["save_dir"])
    best_dice = -1.0
    print(f"Config: {cfg_path.resolve()} | save_dir: {save_dir.resolve()}")

    for epoch in range(1, cfg["train"]["epochs"] + 1):
        train_loss = train_one_epoch(
            model=model,
            loader=train_loader,
            optimizer=optimizer,
            criterion=criterion,
            device=device,
            scaler=scaler,
            use_amp=cfg["train"]["amp"],
        )
        val_metrics = validate(model, val_loader, criterion, device)

        print(
            f"[{epoch:03d}/{cfg['train']['epochs']:03d}] "
            f"train_loss={train_loss:.4f} "
            f"val_loss={val_metrics['loss']:.4f} "
            f"val_dice={val_metrics['dice']:.4f} "
            f"val_iou={val_metrics['iou']:.4f}"
        )

        last_ckpt = save_dir / "last_unet.pth"
        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "epoch": epoch,
                "val_metrics": val_metrics,
                "config": cfg,
            },
            last_ckpt,
        )

        if val_metrics["dice"] > best_dice:
            best_dice = val_metrics["dice"]
            best_ckpt = save_dir / "best_unet.pth"
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "epoch": epoch,
                    "val_metrics": val_metrics,
                    "config": cfg,
                },
                best_ckpt,
            )
            print(f"Saved best checkpoint to {best_ckpt}")


if __name__ == "__main__":
    main()