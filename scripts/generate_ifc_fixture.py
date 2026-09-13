"""Run: uv run --extra bim python scripts/generate_ifc_fixture.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
if __name__ == "__main__":
    from app.adapters.ifc_fixture import generate_ifc_fixture

    for revision in ("V16", "V17"):
        destination = ROOT / "fixtures" / f"harbor-east-{revision.lower()}.ifc"
        generate_ifc_fixture(destination, revision=revision)
        print(destination)
