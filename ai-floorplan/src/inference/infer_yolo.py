from pathlib import Path
import argparse
from ultralytics import YOLO


VALID_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args():
    parser = argparse.ArgumentParser(description="Run YOLO inference on floorplan images")
    parser.add_argument(
        "--weights",
        type=str,
        required=True,
        help="trained weights path, e.g. runs/detect/cubicasa_yolo/weights/best.pt",
    )
    parser.add_argument(
        "--source",
        type=str,
        required=True,
        help="image file or directory",
    )
    parser.add_argument("--imgsz", type=int, default=1024, help="inference image size")
    parser.add_argument("--conf", type=float, default=0.25, help="confidence threshold")
    parser.add_argument("--device", type=str, default="0", help='cuda device id like "0", or "cpu"')
    parser.add_argument("--project", type=str, default="runs/predict", help="save root")
    parser.add_argument("--name", type=str, default="cubicasa_pred", help="run name")
    parser.add_argument("--save_txt", action="store_true", help="save predictions as txt labels")
    parser.add_argument("--save_conf", action="store_true", help="save confidence in txt labels")
    return parser.parse_args()


def collect_sources(source: Path):
    if source.is_file():
        if source.suffix.lower() not in VALID_SUFFIXES:
            raise ValueError(f"Unsupported file type: {source}")
        return [str(source)]

    if source.is_dir():
        files = [str(p) for p in sorted(source.iterdir()) if p.suffix.lower() in VALID_SUFFIXES]
        if not files:
            raise FileNotFoundError(f"No image files found in directory: {source}")
        return files

    raise FileNotFoundError(f"Source not found: {source}")


def main():
    args = parse_args()

    weights_path = Path(args.weights)
    if not weights_path.exists():
        raise FileNotFoundError(f"Weights not found: {weights_path}")

    source_path = Path(args.source)
    sources = collect_sources(source_path)

    model = YOLO(str(weights_path))

    results = model.predict(
        source=sources,
        imgsz=args.imgsz,
        conf=args.conf,
        device=args.device,
        project=args.project,
        name=args.name,
        save=True,
        save_txt=args.save_txt,
        save_conf=args.save_conf,
        verbose=True,
    )

    save_dir = Path(args.project) / args.name
    print("\n[Done] Inference finished.")
    print(f"Predicted images saved to: {save_dir}")


if __name__ == "__main__":
    main()