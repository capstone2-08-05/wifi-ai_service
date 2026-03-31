from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn

from app.core.settings import OUTPUT_DIR, unet_checkpoint_path

UNET_OUTPUT_DIR = OUTPUT_DIR / "unet"
_UNET_MODEL = None
_UNET_DEVICE = "cpu"


class DoubleConv(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class UNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.d1 = DoubleConv(1, 64)
        self.d2 = DoubleConv(64, 128)
        self.d3 = DoubleConv(128, 256)
        self.b = DoubleConv(256, 512)
        self.u3 = nn.ConvTranspose2d(512, 256, 2, stride=2)
        self.c3 = DoubleConv(512, 256)
        self.u2 = nn.ConvTranspose2d(256, 128, 2, stride=2)
        self.c2 = DoubleConv(256, 128)
        self.u1 = nn.ConvTranspose2d(128, 64, 2, stride=2)
        self.c1 = DoubleConv(128, 64)
        self.out = nn.Conv2d(64, 1, 1)
        self.pool = nn.MaxPool2d(2)

    def forward(self, x):
        d1 = self.d1(x)
        d2 = self.d2(self.pool(d1))
        d3 = self.d3(self.pool(d2))
        b = self.b(self.pool(d3))
        u3 = self.u3(b)
        c3 = self.c3(torch.cat([u3, d3], dim=1))
        u2 = self.u2(c3)
        c2 = self.c2(torch.cat([u2, d2], dim=1))
        u1 = self.u1(c2)
        c1 = self.c1(torch.cat([u1, d1], dim=1))
        return self.out(c1)


def _decode_gray(image_bytes: bytes) -> np.ndarray:
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Failed to decode uploaded image bytes")
    return img


def _load_unet_model() -> nn.Module | None:
    global _UNET_MODEL, _UNET_DEVICE
    if _UNET_MODEL is not None:
        return _UNET_MODEL

    ckpt = unet_checkpoint_path()
    if not ckpt:
        return None

    ckpt_path = Path(ckpt)
    if not ckpt_path.exists():
        raise FileNotFoundError(f"UNet checkpoint not found: {ckpt}")

    _UNET_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    ext = ckpt_path.suffix.lower()

    if ext in {".jit", ".ts"}:
        model = torch.jit.load(str(ckpt_path), map_location=_UNET_DEVICE)
        model.eval()
        _UNET_MODEL = model
        return _UNET_MODEL

    model = UNet().to(_UNET_DEVICE)
    state = torch.load(str(ckpt_path), map_location=_UNET_DEVICE)
    if isinstance(state, dict) and "state_dict" in state:
        state = state["state_dict"]
    model.load_state_dict(state, strict=False)
    model.eval()
    _UNET_MODEL = model
    return _UNET_MODEL


def _predict_with_model(model: nn.Module, gray: np.ndarray) -> np.ndarray:
    h, w = gray.shape[:2]
    resized = cv2.resize(gray, (512, 512), interpolation=cv2.INTER_AREA)
    x = resized.astype(np.float32) / 255.0
    x = torch.from_numpy(x).unsqueeze(0).unsqueeze(0).to(_UNET_DEVICE)

    with torch.no_grad():
        logits = model(x)
        prob = torch.sigmoid(logits).squeeze().detach().cpu().numpy()

    binary = (prob > 0.5).astype(np.uint8) * 255
    return cv2.resize(binary, (w, h), interpolation=cv2.INTER_NEAREST)


def _predict_fallback(gray: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    mask = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 5
    )
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=2)


def predict_wall_mask(file_id: str, image_bytes: bytes, filename: str) -> tuple[str, dict]:
    UNET_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    gray = _decode_gray(image_bytes)

    model = _load_unet_model()
    if model is None:
        mask = _predict_fallback(gray)
        model_name = "fallback-morphology"
        note = "Set UNET_CHECKPOINT_PATH for real U-Net inference"
    else:
        mask = _predict_with_model(model, gray)
        model_name = "unet-checkpoint"
        note = "checkpoint inference"

    out = UNET_OUTPUT_DIR / f"{file_id}_mask.png"
    cv2.imwrite(str(out), mask)

    wall_pixels = int((mask > 0).sum())
    total_pixels = int(mask.size)
    connectivity = round(wall_pixels / max(total_pixels, 1), 4)
    metrics = {
        "wallConnectivity": connectivity,
        "model": model_name,
        "device": _UNET_DEVICE,
        "filename": filename,
        "note": note,
    }
    return str(out), metrics
