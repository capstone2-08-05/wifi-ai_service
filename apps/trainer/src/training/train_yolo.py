from pathlib import Path
import argparse
from ultralytics import YOLO


def parse_args():
    parser = argparse.ArgumentParser(description="Train YOLO on CubiCasa-converted dataset")
    parser.add_argument("--data", type=str, default="data/yolo/dataset.yaml", help="dataset yaml path")
    parser.add_argument("--model", type=str, default="yolo11n.pt", help="pretrained model or checkpoint path")
    parser.add_argument("--imgsz", type=int, default=1024, help="image size")
    parser.add_argument("--epochs", type=int, default=100, help="number of epochs")
    parser.add_argument("--batch", type=int, default=8, help="batch size")
    parser.add_argument("--device", type=str, default="0", help='cuda device id like "0", or "cpu"')
    parser.add_argument("--project", type=str, default="runs/detect", help="save root")
    parser.add_argument("--name", type=str, default="cubicasa_yolo", help="run name")
    parser.add_argument("--workers", type=int, default=4, help="dataloader workers")
    parser.add_argument("--patience", type=int, default=20, help="early stopping patience")
    parser.add_argument("--cache", action="store_true", help="cache images in RAM/disk")

    # 추가
    parser.add_argument("--resume", action="store_true", help="resume training from checkpoint")
    parser.add_argument(
        "--save_period",
        type=int,
        default=-1,
        help="save checkpoint every x epochs, disabled if < 1",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset yaml not found: {data_path}")

    model = YOLO(args.model)

    model.train(
        data=str(data_path),
        imgsz=args.imgsz,
        epochs=args.epochs,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        workers=args.workers,
        patience=args.patience,
        cache=args.cache,
        pretrained=not args.resume,
        resume=args.resume,
        save_period=args.save_period,
        verbose=True,
    )

    print("\n[Done] Training finished.")
    print(f"Run dir: {Path(args.project) / args.name}")
    print(f"Best: {Path(args.project) / args.name / 'weights' / 'best.pt'}")
    print(f"Last: {Path(args.project) / args.name / 'weights' / 'last.pt'}")


if __name__ == "__main__":
    main()