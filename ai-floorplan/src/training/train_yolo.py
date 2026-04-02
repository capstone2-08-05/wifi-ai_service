from pathlib import Path
import argparse
from ultralytics import YOLO


def parse_args():
    parser = argparse.ArgumentParser(description="Train YOLO on CubiCasa-converted dataset")
    parser.add_argument("--data", type=str, default="data/yolo/dataset.yaml", help="dataset yaml path")
    parser.add_argument("--model", type=str, default="yolo11n.pt", help="pretrained model path or name")
    parser.add_argument("--imgsz", type=int, default=1024, help="image size")
    parser.add_argument("--epochs", type=int, default=100, help="number of epochs")
    parser.add_argument("--batch", type=int, default=8, help="batch size")
    parser.add_argument("--device", type=str, default="0", help='cuda device id like "0", or "cpu"')
    parser.add_argument("--project", type=str, default="runs/detect", help="save root")
    parser.add_argument("--name", type=str, default="cubicasa_yolo", help="run name")
    parser.add_argument("--workers", type=int, default=4, help="dataloader workers")
    parser.add_argument("--patience", type=int, default=20, help="early stopping patience")
    parser.add_argument("--cache", action="store_true", help="cache images in RAM/disk")
    return parser.parse_args()


def main():
    args = parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset yaml not found: {data_path}")

    model = YOLO(args.model)

    results = model.train(
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
        pretrained=True,
        verbose=True,
    )

    print("\n[Done] Training finished.")
    print(f"Best weights should be under: {Path(args.project) / args.name / 'weights' / 'best.pt'}")
    print(f"Last weights should be under: {Path(args.project) / args.name / 'weights' / 'last.pt'}")


if __name__ == "__main__":
    main()