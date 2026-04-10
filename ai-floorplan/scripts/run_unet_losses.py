"""
Train or infer U-Net once per loss config (same augmentation for all).

Run from repo root `rf-service/ai-floorplan` (or pass --root).

Examples:
  python scripts/run_unet_losses.py train
  python scripts/run_unet_losses.py train --only bce bce_dice
  python scripts/run_unet_losses.py infer --image data/unet/test/test.jpg
  python scripts/run_unet_losses.py infer --image data/unet/test/test.jpg --only focal_tversky
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

# (tag, config path relative to ai-floorplan root)
EXPERIMENTS: list[tuple[str, str]] = [
    ("bce", "configs/unet_bce.yaml"),
    ("bce_dice", "configs/unet_bce_dice.yaml"),
    ("focal_dice", "configs/unet_focal_dice.yaml"),
    ("tversky", "configs/unet_tversky.yaml"),
    ("focal_tversky", "configs/unet_train.yaml"),
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_cfg(root: Path, rel: str) -> dict:
    path = root / rel
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def cmd_train(root: Path, only: set[str] | None) -> int:
    code = 0
    for tag, rel in EXPERIMENTS:
        if only is not None and tag not in only:
            continue
        print(f"\n=== train [{tag}] {rel} ===\n")
        r = subprocess.run(
            [sys.executable, "-m", "src.training.train_unet", "--config", rel],
            cwd=str(root),
        )
        if r.returncode != 0:
            code = r.returncode
    return code


def cmd_infer(root: Path, image: Path, only: set[str] | None, checkpoint_name: str) -> int:
    if not image.is_file():
        print(f"Image not found: {image}", file=sys.stderr)
        return 1

    image_abs = image.resolve()
    code = 0
    for tag, rel in EXPERIMENTS:
        if only is not None and tag not in only:
            continue
        cfg = _load_cfg(root, rel)
        save_dir = Path(cfg["train"]["save_dir"])
        ckpt = (root / save_dir / checkpoint_name).resolve()
        if not ckpt.is_file():
            print(f"[skip {tag}] missing checkpoint: {ckpt}")
            continue
        out_dir = root / "outputs" / "unet_infer" / tag
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== infer [{tag}] -> {out_dir} ===\n")
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.inference.infer_unet",
                "--image",
                str(image_abs),
                "--checkpoint",
                str(ckpt),
                "--config",
                rel,
                "--out_dir",
                str(out_dir),
            ],
            cwd=str(root),
        )
        if r.returncode != 0:
            code = r.returncode
    return code


def main() -> None:
    root = _repo_root()
    p = argparse.ArgumentParser(description="Batch train/infer U-Net by loss config.")
    sub = p.add_subparsers(dest="command", required=True)

    pt = sub.add_parser("train", help="Run training for each loss experiment")
    pt.add_argument(
        "--only",
        nargs="+",
        choices=[t for t, _ in EXPERIMENTS],
        help="Subset of experiment tags (default: all)",
    )
    pt.add_argument(
        "--root",
        type=Path,
        default=root,
        help="ai-floorplan root (default: auto)",
    )

    pi = sub.add_parser("infer", help="Run inference for each trained checkpoint")
    pi.add_argument("--image", type=Path, required=True)
    pi.add_argument(
        "--only",
        nargs="+",
        choices=[t for t, _ in EXPERIMENTS],
        help="Subset of experiment tags (default: all)",
    )
    pi.add_argument(
        "--checkpoint",
        type=str,
        default="best_unet.pth",
        help="Checkpoint file name inside each save_dir (default: best_unet.pth)",
    )
    pi.add_argument("--root", type=Path, default=root, help="ai-floorplan root (default: auto)")

    args = p.parse_args()
    root = Path(args.root).resolve()

    only_set = set(args.only) if getattr(args, "only", None) else None

    if args.command == "train":
        sys.exit(cmd_train(root, only_set))
    if args.command == "infer":
        sys.exit(cmd_infer(root, Path(args.image), only_set, args.checkpoint))
    sys.exit(1)


if __name__ == "__main__":
    main()
