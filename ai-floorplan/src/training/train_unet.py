from __future__ import annotations

import argparse
import csv
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

from src.datasets.wall_dataset import FloorplanWallDataset
from src.models.unet import UNet
from src.training.losses import build_loss
from src.utils.common import ensure_dir, get_device, load_yaml, set_seed
from src.utils.metrics import dice_score_from_logits, iou_score_from_logits


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--resume_path", type=str, default=None)
    return parser.parse_args()


def train_one_epoch(model, loader, optimizer, criterion, device, scaler, use_amp: bool):
    model.train()
    total_loss = 0.0

    for images, masks in tqdm(loader, desc="train", leave=False):
        images = images.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)

        with torch.amp.autocast(device_type=device.type, enabled=use_amp):
            logits = model(images)
            loss = criterion(logits, masks)

        if use_amp:
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            optimizer.step()

        total_loss += loss.item()

    return total_loss / max(len(loader), 1)


@torch.no_grad()
def validate(model, loader, criterion, device):
    model.eval()

    total_loss = 0.0
    total_dice = 0.0
    total_iou = 0.0

    for images, masks in tqdm(loader, desc="val", leave=False):
        images = images.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)

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


def main():
    args = parse_args()
    cfg = load_yaml(args.config)

    set_seed(cfg["seed"])
    device = get_device()
    use_amp = bool(cfg["train"].get("amp", True)) and device.type == "cuda"

    print("CONFIG PATH:", args.config)
    print("LOSS NAME:", cfg["train"]["loss_name"])
    print("AUGMENT:", cfg["data"]["augment"])

    train_ds = FloorplanWallDataset(
        image_dir=cfg["data"]["train_image_dir"],
        mask_dir=cfg["data"]["train_mask_dir"],
        image_size=cfg["data"]["image_size"],
        augment=cfg["data"].get("augment", False),
    )
    val_ds = FloorplanWallDataset(
        image_dir=cfg["data"]["val_image_dir"],
        mask_dir=cfg["data"]["val_mask_dir"],
        image_size=cfg["data"]["image_size"],
        augment=False,
    )

    train_loader = DataLoader(
        train_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=True,
        num_workers=cfg["train"]["num_workers"],
        pin_memory=(device.type == "cuda"),
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=False,
        num_workers=cfg["train"]["num_workers"],
        pin_memory=(device.type == "cuda"),
    )

    model = UNet(
        in_channels=cfg["model"]["in_channels"],
        out_channels=cfg["model"]["out_channels"],
    ).to(device)

    criterion = build_loss(cfg["train"]["loss_name"])
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["train"]["lr"])
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    save_dir = ensure_dir(cfg["train"]["save_dir"])
    log_csv_path = save_dir / "train_log.csv"
    last_ckpt_path = Path(args.resume_path) if args.resume_path else save_dir / "last_unet.pth"
    best_ckpt_path = save_dir / "best_unet.pth"

    if not log_csv_path.exists():
        with open(log_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "epoch",
                    "train_loss",
                    "val_loss",
                    "val_dice",
                    "val_iou",
                    "best_dice",
                ]
            )

    start_epoch = 1
    best_dice = -1.0

    if args.resume:
        if not last_ckpt_path.exists():
            raise FileNotFoundError(f"Resume checkpoint not found: {last_ckpt_path}")

        print(f"Resuming from: {last_ckpt_path}")
        ckpt = torch.load(last_ckpt_path, map_location=device)

        model.load_state_dict(ckpt["model_state_dict"])
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])

        scaler_state = ckpt.get("scaler_state_dict")
        if scaler_state is not None and use_amp:
            scaler.load_state_dict(scaler_state)

        start_epoch = ckpt["epoch"] + 1
        best_dice = ckpt.get("best_dice", -1.0)

        print(f"Resume start epoch: {start_epoch}")
        print(f"Loaded best_dice: {best_dice:.4f}")

    for epoch in range(start_epoch, cfg["train"]["epochs"] + 1):
        train_loss = train_one_epoch(
            model=model,
            loader=train_loader,
            optimizer=optimizer,
            criterion=criterion,
            device=device,
            scaler=scaler,
            use_amp=use_amp,
        )

        val_metrics = validate(
            model=model,
            loader=val_loader,
            criterion=criterion,
            device=device,
        )

        if val_metrics["dice"] > best_dice:
            best_dice = val_metrics["dice"]

            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "scaler_state_dict": scaler.state_dict() if use_amp else None,
                    "best_dice": best_dice,
                    "val_metrics": val_metrics,
                    "config": cfg,
                },
                best_ckpt_path,
            )
            print(f"Saved best checkpoint to {best_ckpt_path}")

        torch.save(
            {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "scaler_state_dict": scaler.state_dict() if use_amp else None,
                "best_dice": best_dice,
                "val_metrics": val_metrics,
                "config": cfg,
            },
            last_ckpt_path,
        )

        with open(log_csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    epoch,
                    train_loss,
                    val_metrics["loss"],
                    val_metrics["dice"],
                    val_metrics["iou"],
                    best_dice,
                ]
            )

        print(
            f"[{epoch:03d}/{cfg['train']['epochs']:03d}] "
            f"train_loss={train_loss:.4f} "
            f"val_loss={val_metrics['loss']:.4f} "
            f"val_dice={val_metrics['dice']:.4f} "
            f"val_iou={val_metrics['iou']:.4f}"
        )

    print("Training finished.")


if __name__ == "__main__":
    main()