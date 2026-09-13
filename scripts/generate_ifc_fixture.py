"""Run: uv run --extra bim python scripts/generate_ifc_fixture.py"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
if __name__ == "__main__":
    from app.adapters.ifc_fixture import generate_ifc_fixture

    v16 = ROOT / "fixtures" / "harbor-east-v16.ifc"
    generate_ifc_fixture(v16, revision="V16")
    print(v16)
    # Keep the baseline filename used by the existing WebGL end-to-end test as an
    # exact byte-for-byte alias of the generated V16 artifact.
    baseline = ROOT / "fixtures" / "harbor-east.ifc"
    shutil.copyfile(v16, baseline)
    print(baseline)
    v17 = ROOT / "fixtures" / "harbor-east-v17.ifc"
    generate_ifc_fixture(v17, revision="V17")
    print(v17)
