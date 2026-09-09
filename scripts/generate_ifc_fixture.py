"""Run: uv run --extra bim python scripts/generate_ifc_fixture.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
if __name__ == "__main__":
    from app.adapters.ifc_fixture import generate_ifc_fixture

    destination = ROOT / "fixtures" / "harbor-east.ifc"
    generate_ifc_fixture(destination)
    print(destination)
