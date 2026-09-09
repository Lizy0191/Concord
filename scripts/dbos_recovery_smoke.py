"""Real DBOS retry/recovery verification, with controlled application failures.

Requires the installed DBOS SDK. This script never substitutes the diagnostic
runtime and never calls paid providers. The separate HTTP smoke checks process kill.
"""

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def wait_for(predicate, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError("DBOS did not reach the required persisted state before the deadline")


def exercise(folder: Path) -> dict:
    if importlib.util.find_spec("dbos") is None:
        raise RuntimeError(
            "DBOS is required; install core dependencies. No diagnostic fallback is used."
        )
    from app.api.main import create_app
    from app.bootstrap import build_services
    from app.domain.errors import ProviderError
    from app.settings import Settings
    from fastapi.testclient import TestClient

    settings = Settings(
        data_dir=folder,
        _env_file=None,
        diagnostic_runtime=False,
        reasoning="offline",
        runtime="dbos",
        storage="local",
    )
    services = build_services(settings)
    checks = []
    original = services.analysis.analyze

    def injected_failure(_, *, generation=None):
        raise ProviderError("Injected recovery fixture failure")

    try:
        with TestClient(create_app(settings, services)) as client:
            client.headers["Authorization"] = "Bearer local-demo-admin"

            def state(run_id):
                with services.factory.open() as repo:
                    return repo.run(run_id)

            def workspace():
                response = client.get("/api/projects/harbor-east/workspace")
                response.raise_for_status()
                return response.json()

            wait_for(lambda: workspace()["analysis"] is not None)
            for kind, package, change, fail_after_commit in [
                ("design_revision", "WP-200", {"revision": "V17"}, False),
                ("workforce", "WP-300", {"available_workers": 1}, True),
            ]:
                if not fail_after_commit:
                    services.analysis.analyze = injected_failure
                response = client.post(
                    "/api/projects/harbor-east/events",
                    json={
                        "project_id": "harbor-east",
                        "work_package_id": package,
                        "kind": kind,
                        "title": "DBOS recovery fixture",
                        "change": change,
                    },
                )
                assert response.status_code == 202, response.text
                run_id = response.json()["id"]
                if not fail_after_commit:
                    wait_for(lambda run_id=run_id: services.runtime.status(run_id) == "ERROR")
                    assert state(run_id).status == "FAILED"
                    services.analysis.analyze = original
                    response = client.post(f"/api/runs/{run_id}/resume")
                    assert response.status_code == 202, response.text
                    wait_for(lambda run_id=run_id: state(run_id).status == "WAITING_APPROVAL")
                    assert state(run_id).runtime_execution_id != run_id
                    checks.append("errored-execution-retry-with-persisted-identity")
                else:
                    wait_for(lambda run_id=run_id: state(run_id).status == "WAITING_APPROVAL")
                proposal = next(
                    item for item in workspace()["proposals"] if item["work_package_id"] == package
                )
                assert (
                    client.post(f"/api/proposals/{proposal['id']}/approve", json={}).status_code
                    == 200
                )
                if fail_after_commit:
                    services.analysis.analyze = injected_failure
                assert client.post(f"/api/proposals/{proposal['id']}/execute").status_code == 202
                if fail_after_commit:
                    wait_for(lambda run_id=run_id: services.runtime.status(run_id) == "ERROR")
                    assert state(run_id).status == "FAILED"
                    receipt = client.get(f"/api/operations/{proposal['operation_id']}").json()
                    assert receipt["operation_id"] == proposal["operation_id"]
                    services.analysis.analyze = original
                    retry = client.post(f"/api/proposals/{proposal['id']}/execute")
                    assert retry.status_code == 202, retry.text
                    wait_for(lambda run_id=run_id: state(run_id).status == "COMPLETED")
                    assert (
                        client.get(f"/api/operations/{proposal['operation_id']}").json() == receipt
                    )
                    assert workspace()["state"]["version"] == receipt["after_version"]
                    checks.append(
                        "committed-effect-failed-recheck-recovery-without-duplicate-effect"
                    )
                else:
                    wait_for(lambda run_id=run_id: state(run_id).status == "COMPLETED")
                assert all(
                    item["status"] == "READY" for item in workspace()["analysis"]["readiness"]
                )
                with services.factory.open() as repo:
                    records = [
                        item
                        for item in repo.audits("harbor-east")
                        if item.action == "ACTION_VERIFIED" and item.run_id == run_id
                    ]
                    assert len(records) == 1
                checks.append(f"{kind}-one-receipt-fresh-ready")
        return {"status": "PASS", "runtime": "dbos", "checks": checks}
    finally:
        services.analysis.analyze = original
        services.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    for key in list(os.environ):
        if key.startswith("CCA_"):
            del os.environ[key]
    workspace = ROOT / ".verification-work"
    workspace.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=workspace, prefix="dbos-recovery-") as folder:
        result = exercise(Path(folder))
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
