"""Execute real durable SDKs in separate processes; missing SDKs explicitly skip."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "script, arguments",
    [
        ("http_smoke.py", ["--runtime", "dbos", "--crash-restart"]),
        ("dbos_recovery_smoke.py", []),
    ],
)
def test_real_dbos_recovery(script, arguments):
    pytest.importorskip("dbos")
    env = {key: value for key, value in os.environ.items() if not key.startswith("CCA_")}
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *arguments],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=150,
    )
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-6000:]
    assert '"status": "PASS"' in result.stdout
    assert '"runtime": "dbos"' in result.stdout


def test_real_temporal_worker_process_recovery():
    pytest.importorskip("temporalio")
    if os.environ.get("CCA_TEST_TEMPORAL_LOCAL") != "1":
        pytest.skip("Set CCA_TEST_TEMPORAL_LOCAL=1 to run the real local Temporal server")
    binary = os.environ.get("CCA_TEST_TEMPORAL_SERVER_BINARY")
    if not binary:
        pytest.fail(
            "Set CCA_TEST_TEMPORAL_SERVER_BINARY to the explicitly provisioned Temporal CLI"
        )
    binary_path = Path(binary)
    if not binary_path.is_file() or not os.access(binary_path, os.X_OK):
        pytest.fail(f"Temporal CLI is not executable: {binary_path}")
    env = {key: value for key, value in os.environ.items() if not key.startswith("CCA_")}
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/temporal_recovery_smoke.py"),
            "--existing-server-binary",
            str(binary_path),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-6000:]
    assert '"status": "PASS"' in result.stdout
    assert '"runtime": "temporal"' in result.stdout
