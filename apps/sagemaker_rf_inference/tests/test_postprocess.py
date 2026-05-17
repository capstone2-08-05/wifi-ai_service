"""postprocess.py unit tests."""
from __future__ import annotations

import numpy as np
import pytest

from app.postprocess import encode_heatmap_png


def test_encode_heatmap_returns_png_bytes():
    dbm = np.linspace(-95, -35, 20 * 30, dtype=np.float32).reshape(20, 30)
    png = encode_heatmap_png(dbm)
    assert isinstance(png, bytes)
    # PNG magic bytes
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_encode_heatmap_invalid_cells_transparent():
    # half valid half invalid
    dbm = np.full((10, 10), -50.0, dtype=np.float32)
    dbm[:5, :] = -300.0  # invalid (below INVALID_DBM_THRESHOLD = -200)

    import cv2
    png = encode_heatmap_png(dbm)
    decoded = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
    assert decoded.shape == (10, 10, 4)  # RGBA
    # invalid cells alpha=0
    assert decoded[:5, :, 3].max() == 0
    # valid cells alpha=255
    assert decoded[5:, :, 3].min() == 255


def test_encode_heatmap_rejects_non_2d():
    with pytest.raises(ValueError):
        encode_heatmap_png(np.zeros((3, 4, 5), dtype=np.float32))
