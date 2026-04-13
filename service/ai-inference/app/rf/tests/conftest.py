"""RF 테스트: ai-inference 루트 + `app/rf` 를 path 에 넣는다 (`app.*` 패키지 + flat `rf_models` 등)."""

from __future__ import annotations

import sys
from pathlib import Path

_AI = Path(__file__).resolve().parents[3]
_RF = _AI / "app" / "rf"
for _p in (_AI, _RF):
    s = str(_p.resolve())
    if s not in sys.path:
        sys.path.insert(0, s)
