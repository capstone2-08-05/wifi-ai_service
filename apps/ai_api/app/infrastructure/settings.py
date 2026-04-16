import os
from pathlib import Path

from dotenv import load_dotenv
import yaml

# app/infrastructure/settings.py -> parents[2] == apps/ai_api
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

OUTPUT_DIR = ROOT_DIR / "data" / "output"
_SIONNA_CFG: dict | None = None


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


def sionna_config_path() -> str:
    default_cfg = ROOT_DIR / "configs" / "sionna_inference.yaml"
    return os.getenv("SIONNA_CONFIG_PATH", str(default_cfg)).strip()


def _load_sionna_config() -> dict:
    global _SIONNA_CFG
    if _SIONNA_CFG is not None:
        return _SIONNA_CFG

    cfg_path = Path(sionna_config_path())
    if not cfg_path.exists():
        _SIONNA_CFG = {}
        return _SIONNA_CFG

    with open(cfg_path, encoding="utf-8") as f:
        _SIONNA_CFG = yaml.safe_load(f) or {}
    return _SIONNA_CFG


def sionna_cell_size_m() -> float:
    cfg = _load_sionna_config()
    infer_cfg = cfg.get("infer", {})
    default_value = infer_cfg.get("cell_size_m", 0.25)
    return float(os.getenv("SIONNA_CELL_SIZE_M", str(default_value)))


def sionna_samples_per_tx() -> int:
    cfg = _load_sionna_config()
    infer_cfg = cfg.get("infer", {})
    default_value = infer_cfg.get("samples_per_tx", 100000)
    return int(os.getenv("SIONNA_SAMPLES_PER_TX", str(default_value)))


def sionna_seed() -> int:
    cfg = _load_sionna_config()
    infer_cfg = cfg.get("infer", {})
    default_value = infer_cfg.get("seed", 42)
    return int(os.getenv("SIONNA_SEED", str(default_value)))


def sionna_device() -> str:
    cfg = _load_sionna_config()
    infer_cfg = cfg.get("infer", {})
    default_value = str(infer_cfg.get("device", "")).strip()
    return os.getenv("SIONNA_DEVICE", default_value).strip()
