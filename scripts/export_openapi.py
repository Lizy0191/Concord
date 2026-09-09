"""Export schemas without starting runtimes, opening a DB or reading user config."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from verification_context import isolated_configuration

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "frontend/openapi.json")
    output = parser.parse_args().output.resolve()
    work = ROOT / ".verification-work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work, prefix="schema-") as folder:
        with isolated_configuration(Path(folder)):
            from app.api.main import create_app
            from app.settings import Settings

            schema = create_app(Settings(_env_file=None)).openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {output.name}")


if __name__ == "__main__":
    main()
