"""Isolated real API + built React host for Playwright. Never reuses user data."""

import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise SystemExit("Build the actual React application first: cd frontend && pnpm build")
    runtime = os.environ.get("CCA_E2E_RUNTIME", "dbos")
    if runtime not in {"dbos", "diagnostic"}:
        raise SystemExit("CCA_E2E_RUNTIME must be dbos or explicit diagnostic")
    workspace = ROOT / ".verification-work"
    workspace.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=workspace, prefix="playwright-") as folder:
        environment = {
            key: value for key, value in os.environ.items() if not key.startswith("CCA_")
        }
        environment.update(
            PYTHONPATH=str(ROOT / "backend"),
            PYTHONUNBUFFERED="1",
            CCA_DATA_DIR=folder,
            CCA_PROFILE="local",
            CCA_API_TOKEN="local-demo-admin",
            CCA_RUNTIME="dbos",
        )
        command = [
            sys.executable,
            "-m",
            "app.cli",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            os.environ.get("CCA_E2E_PORT", "18000"),
        ]
        if runtime == "diagnostic":
            command.append("--diagnostic-runtime")
        # Run from the temporary directory so a user's root .env cannot alter this fixture.
        process = subprocess.Popen(command, cwd=folder, env=environment)

        def stop(_signal, _frame):
            if process.poll() is None:
                process.terminate()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        try:
            return process.wait()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
