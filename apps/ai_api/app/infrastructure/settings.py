import os
from pathlib import Path

from dotenv import load_dotenv

# app/infrastructure/settings.py -> parents[2] == apps/ai_api
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

OUTPUT_DIR = ROOT_DIR / "data" / "output"


def preload_models() -> bool:
    return os.getenv("PRELOAD_MODELS", "false").strip().lower() in {"1", "true", "yes", "on"}


def default_device() -> str:
    return os.getenv("DEFAULT_DEVICE", "auto").strip().lower()


def unet_checkpoint_path() -> str:
    return os.getenv("UNET_CHECKPOINT_PATH", "").strip()


def unet_config_path() -> str:
    default_cfg = ROOT_DIR / "configs" / "unet_inference.yaml"
    return os.getenv("UNET_CONFIG_PATH", str(default_cfg)).strip()


def yolo_model_path() -> str:
    return os.getenv("YOLO_MODEL_PATH", "yolov8n.pt").strip()


def yolo_config_path() -> str:
    default_cfg = ROOT_DIR / "configs" / "yolo_inference.yaml"
    return os.getenv("YOLO_CONFIG_PATH", str(default_cfg)).strip()


def yolo_conf_threshold() -> float:
    return float(os.getenv("YOLO_CONF_THRESHOLD", "0.25"))


def yolo_device() -> str:
    return os.getenv("YOLO_DEVICE", "").strip()


def sionna_cell_size_m() -> float:
    return float(os.getenv("SIONNA_CELL_SIZE_M", "0.5"))


def sionna_samples_per_tx() -> int:
    return int(os.getenv("SIONNA_SAMPLES_PER_TX", "100000"))


def sionna_seed() -> int:
    return int(os.getenv("SIONNA_SEED", "42"))
