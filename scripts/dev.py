"""Start the default local API and Vite, and supervise both child processes."""

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        print(
            "pnpm is required. Install pnpm 10, then run pnpm install in frontend.", file=sys.stderr
        )
        return 2
    env = {**os.environ, "PYTHONPATH": str(ROOT / "backend"), "PYTHONUNBUFFERED": "1"}
    processes = []
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True
        for process in processes:
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        processes.append(
            subprocess.Popen([sys.executable, "-m", "app.cli", "serve"], cwd=ROOT, env=env)
        )
        processes.append(
            subprocess.Popen([pnpm, "dev", "--host", "127.0.0.1"], cwd=ROOT / "frontend", env=env)
        )
        print("Web: http://127.0.0.1:5173 | API: http://127.0.0.1:8000", flush=True)
        while not stopping and all(p.poll() is None for p in processes):
            time.sleep(0.3)
        return next((p.returncode for p in processes if p.returncode not in (None, 0)), 0)
    finally:
        stop()
        for process in processes:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
