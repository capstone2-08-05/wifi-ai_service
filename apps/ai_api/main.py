import sys
from pathlib import Path

# Preferred entrypoint bootstrap: keep repository packages importable.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT_STR = str(_REPO_ROOT)
if _REPO_ROOT_STR not in sys.path:
    sys.path.insert(0, _REPO_ROOT_STR)

from app.main import app
