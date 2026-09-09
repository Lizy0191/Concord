"""Generate original UI fixtures with isolated local settings and no cloud egress."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from verification_context import isolated_configuration

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def generate(folder: Path) -> dict:
    from app.api.main import create_app
    from app.bootstrap import build_services
    from app.settings import Settings
    from fastapi.testclient import TestClient

    settings = Settings(data_dir=folder, diagnostic_runtime=True, _env_file=None)
    services = build_services(settings)
    try:
        with TestClient(create_app(settings, services)) as client:
            client.headers["Authorization"] = "Bearer local-demo-admin"
            response = client.post(
                "/api/projects/harbor-east/events",
                json={
                    "project_id": "harbor-east",
                    "work_package_id": "WP-200",
                    "kind": "inspection",
                    "title": "Synthetic UI fixture inspection",
                    "change": {"inspection_passed": False},
                },
            )
            response.raise_for_status()
            waiting = client.get("/api/projects/harbor-east/workspace").json()
            proposal = next(p for p in waiting["proposals"] if p["work_package_id"] == "WP-200")
            assert proposal["risk"] == 4
            approval = client.post(
                f"/api/proposals/{proposal['id']}/approve",
                json={
                    "strong": True,
                    "confirmation": "APPROVE R4",
                },
            )
            approval.raise_for_status()
            return {"waiting": waiting, "approval": approval.json()}
    finally:
        services.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "frontend/tests/fixtures/inspector.json"
    )
    target = parser.parse_args().output.resolve()
    work = ROOT / ".verification-work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work, prefix="ui-fixtures-") as folder:
        with isolated_configuration(Path(folder)):
            output = generate(Path(folder))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Generated synthetic API fixture: {target.name}")


if __name__ == "__main__":
    main()
