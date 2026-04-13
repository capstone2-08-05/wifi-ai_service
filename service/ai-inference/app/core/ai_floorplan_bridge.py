from __future__ import annotations

import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[2]
RF_SERVICE_ROOT = SERVICE_ROOT.parent.parent
AI_FLOORPLAN_ROOT = RF_SERVICE_ROOT / "ai-floorplan"

# Allow importing ai-floorplan's "src.*" modules from the service app.
if str(AI_FLOORPLAN_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_FLOORPLAN_ROOT))

