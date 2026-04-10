from __future__ import annotations

import argparse
import csv
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

from src.datasets.wall_dataset import FloorplanWallDataset
from src.models.unet import UNet
from src.utils.common import ensure_dir, get_device, load_yaml, set_seed
from src.utils.losses import build_loss
from src.utils.metrics import dice_score_from_logits, iou_score_from_logits


def parse_args():
    p = argparse.ArgumentParser(description="Train U-Net wall segmentation.")
    p.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to YAML config",
    )
    p.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Path to checkpoint to resume from (e.g., checkpoints/unet_bce/last_unet.pth)",
    )
    return p.parse_args()


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
    cfg_path = Path(args.config)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Config not found: {cfg_path.resolve()}")
    cfg = load_yaml(str(cfg_path))
    set_seed(cfg["seed"])
    device = get_device()
    use_amp = bool(cfg["train"].get("amp", True)) and device.type == "cuda"

    print("CONFIG PATH:", str(cfg_path))
    print("LOSS:", cfg.get("loss", {}).get("name", cfg.get("train", {}).get("loss_name", "bce")))

    aug_cfg = cfg.get("augment") or {}
    data_cfg = cfg["data"]
    augment_enabled = bool(
        aug_cfg.get("enabled", data_cfg.get("augment", bool(aug_cfg)))
    )
    train_ds = FloorplanWallDataset(
        image_dir=data_cfg["train_image_dir"],
        mask_dir=data_cfg["train_mask_dir"],
        image_size=data_cfg["image_size"],
        augment=augment_enabled,
        resize_mode=data_cfg.get("resize_mode", "letterbox"),
        patch_size=data_cfg.get("train_patch_size"),
        wall_focus_prob=data_cfg.get("wall_focus_prob", 0.7),
        min_wall_ratio=data_cfg.get("min_wall_ratio", 0.01),
        patch_max_tries=data_cfg.get("patch_max_tries", 10),
        flip_h_prob=float(aug_cfg.get("flip_h_prob", 0.5)),
        flip_v_prob=float(aug_cfg.get("flip_v_prob", 0.2)),
    )
    val_ds = FloorplanWallDataset(
        image_dir=data_cfg["val_image_dir"],
        mask_dir=data_cfg["val_mask_dir"],
        image_size=data_cfg["image_size"],
        augment=False,
        resize_mode=data_cfg.get("resize_mode", "letterbox"),
        patch_size=data_cfg.get("val_patch_size"),
        wall_focus_prob=data_cfg.get("wall_focus_prob", 0.7),
        min_wall_ratio=data_cfg.get("min_wall_ratio", 0.01),
        patch_max_tries=data_cfg.get("patch_max_tries", 10),
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

    loss_cfg = cfg.get("loss")
    if loss_cfg is None:
        # Backward compatibility for legacy config shape.
        loss_cfg = {"name": cfg.get("train", {}).get("loss_name", "bce")}
    criterion = build_loss(loss_cfg)
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["train"]["lr"])
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    save_dir = ensure_dir(cfg["train"]["save_dir"])
    log_csv_path = save_dir / "train_log.csv"
    last_ckpt_path = save_dir / "last_unet.pth"
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
    metrics_path = save_dir / "metrics.csv"
    if not metrics_path.exists():
        with open(metrics_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["epoch", "train_loss", "val_loss", "val_dice", "val_iou"])

    if args.resume is not None:
        resume_path = Path(args.resume)
        if not resume_path.is_file():
            raise FileNotFoundError(f"Resume checkpoint not found: {resume_path.resolve()}")
        ckpt = torch.load(str(resume_path), map_location=device)
        model.load_state_dict(ckpt["model_state_dict"])
        if "optimizer_state_dict" in ckpt:
            optimizer.load_state_dict(ckpt["optimizer_state_dict"])
        if "scaler_state_dict" in ckpt and cfg["train"]["amp"]:
            scaler.load_state_dict(ckpt["scaler_state_dict"])
        start_epoch = int(ckpt.get("epoch", 0)) + 1
        if "best_dice" in ckpt:
            best_dice = float(ckpt["best_dice"])
        elif "val_metrics" in ckpt and "dice" in ckpt["val_metrics"]:
            best_dice = float(ckpt["val_metrics"]["dice"])
        print(
            f"Resumed from {resume_path.resolve()} "
            f"(next_epoch={start_epoch}, best_dice={best_dice:.4f})"
        )

    print(f"Config: {cfg_path.resolve()} | save_dir: {save_dir.resolve()}")

    if start_epoch > cfg["train"]["epochs"]:
        print(
            f"Nothing to do: start_epoch={start_epoch} exceeds configured epochs={cfg['train']['epochs']}."
        )
        return

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
        with open(metrics_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    epoch,
                    f"{train_loss:.6f}",
                    f"{val_metrics['loss']:.6f}",
                    f"{val_metrics['dice']:.6f}",
                    f"{val_metrics['iou']:.6f}",
                ]
            )

    print("Training finished.")


if __name__ == "__main__":
    main()