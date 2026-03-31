import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

OUTPUT_DIR = ROOT_DIR / "data" / "output"


def unet_checkpoint_path() -> str:
    return os.getenv("UNET_CHECKPOINT_PATH", "").strip()


def yolo_model_path() -> str:
    return os.getenv("YOLO_MODEL_PATH", "yolov8n.pt").strip()


def yolo_conf_threshold() -> float:
    return float(os.getenv("YOLO_CONF_THRESHOLD", "0.25"))


def yolo_device() -> str:
    return os.getenv("YOLO_DEVICE", "").strip()
