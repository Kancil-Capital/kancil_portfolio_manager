"""
scripts/export_openapi.py
Write the FastAPI OpenAPI spec to frontend/openapi.json without starting the server
(importing the app loads no models; those load in the lifespan handler).
Run via `bun run generate` in frontend/, which then runs orval on the file.
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.disable(logging.CRITICAL)

from main import app

OUT = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"

# Same compact format FastAPI serves at /openapi.json, so diffs stay minimal
OUT.write_text(json.dumps(app.openapi(), separators=(",", ":"), ensure_ascii=False))
print(f"Wrote {OUT}")
