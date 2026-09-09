"""Run the real HTTP crash/restart contract using a local Temporal dev server.

The SDK may download its upstream dev-server binary. Running this command is an
explicit opt-in to that download; ordinary offline tests never invoke it.
"""

import argparse
import asyncio
import importlib.util
import json
import os
import socket
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


async def exercise(existing: Path | None = None) -> dict:
    if existing and (not existing.is_file() or not os.access(existing, os.X_OK)):
        raise RuntimeError(f"Temporal CLI is not executable: {existing}")
    if importlib.util.find_spec("temporalio") is None:
        raise RuntimeError("Install the temporal extra; no diagnostic fallback is used")
    from temporalio.testing import WorkflowEnvironment

    workspace = ROOT / ".verification-work"
    workspace.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="temporal-", dir=workspace) as folder:
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        kwargs = {"dev_server_existing_path": str(existing.resolve())} if existing else {}
        async with await WorkflowEnvironment.start_local(
            ip="127.0.0.1",
            port=port,
            ui=False,
            dev_server_database_filename=str(Path(folder) / "temporal.db"),
            download_dest_dir=str(workspace / "temporal-sdk"),
            **kwargs,
        ):
            command = [
                sys.executable,
                str(ROOT / "scripts/http_smoke.py"),
                "--runtime",
                "temporal",
                "--temporal-address",
                f"127.0.0.1:{port}",
                "--crash-restart",
            ]
            process = await asyncio.create_subprocess_exec(
                *command, cwd=ROOT, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=150)
            except BaseException:
                if process.returncode is None:
                    process.kill()
                await process.communicate()
                raise
            if process.returncode:
                raise RuntimeError(stdout.decode()[-4000:] + stderr.decode()[-4000:])
            result = json.loads(stdout)
            assert result["status"] == "PASS" and result["runtime"] == "temporal"
            result["checks"].append("real-temporal-worker-process-recovery")
            return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--existing-server-binary", type=Path, help="Use an installed Temporal CLI; do not download"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(exercise(args.existing_server_binary))
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
