"""pytest 수집 시 ai-inference 루트와 ``app/rf`` 를 ``sys.path`` 에 추가."""

from __future__ import annotations

import sys
from pathlib import Path

_AI = Path(__file__).resolve().parents[3]
_RF = _AI / "app" / "rf"
for _p in (_AI, _RF):
    s = str(_p.resolve())
    if s not in sys.path:
        sys.path.insert(0, s)
