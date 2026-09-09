"""Exercise production TypeScript HTTP/SSE modules against an isolated real API.

No frontend dependency installation is needed for Node's type stripping. This does
not render React or replace Playwright. DBOS is the default; diagnostic is explicit.
"""

import argparse
import json
import os
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path

from http_smoke import ROOT, Server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", choices=["dbos", "diagnostic"], default="dbos")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    node = shutil.which("node")
    if node is None:
        parser.error("Node 22.6+ is required")
    work = ROOT / ".verification-work"
    work.mkdir(exist_ok=True)
    token = secrets.token_urlsafe(40)
    with tempfile.TemporaryDirectory(dir=work, prefix="node-api-") as folder:
        server = Server(Path(folder), args.runtime, token)
        try:
            env = {key: value for key, value in os.environ.items() if not key.startswith("CCA_")}
            env.update(
                CCA_SMOKE_ENDPOINT=server.url,
                CCA_SMOKE_TOKEN=token,
                CCA_SMOKE_RUNTIME="diagnostic-NON-DURABLE"
                if args.runtime == "diagnostic"
                else "dbos",
            )
            result = subprocess.run(
                [
                    node,
                    "--experimental-strip-types",
                    str(ROOT / "frontend/tests/live-api-smoke.mjs"),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                timeout=90,
            )
            if result.returncode:
                raise RuntimeError(
                    "Production client HTTP contract failed:\n" + result.stdout + result.stderr
                )
            report = json.loads(result.stdout)
            assert report["status"] == "PASS" and len(report["checks"]) >= 9
        finally:
            server.close()
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
