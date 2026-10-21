"""AC-133: write the backend OpenAPI document for frontend type generation.

Usage (from backend/): python scripts/export_openapi.py ../frontend/src/api/openapi.json
CI regenerates it and fails if the committed copy, or the types built from it, differ.
"""

import json
import sys
from pathlib import Path

from app.main import app


def main(out: str) -> None:
    doc = app.openapi()
    Path(out).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(doc['paths'])} paths)")


if __name__ == "__main__":
    main(sys.argv[1])
