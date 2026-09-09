"""Build the existing native shell and its Python sidecar on the target OS.

This is a native build, not a Windows cross-compiler for WSL. Dependencies and
platform system libraries must already be installed. No package registry mutation
or installation happens here.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cli_command(root: Path) -> list[str]:
    node = shutil.which("node")
    package = root / "frontend/node_modules/@tauri-apps/cli/package.json"
    if node is None or not package.is_file():
        raise RuntimeError("Install Node and frontend dependencies, including @tauri-apps/cli")
    value = json.loads(package.read_text(encoding="utf-8")).get("bin")
    relative = value.get("tauri") if isinstance(value, dict) else value
    if not isinstance(relative, str):
        raise RuntimeError("Installed Tauri CLI does not declare its tauri executable")
    executable = (package.parent / relative).resolve()
    if not executable.is_relative_to(package.parent.resolve()) or not executable.is_file():
        raise RuntimeError("Installed Tauri CLI executable is missing or outside its package")
    return [node, str(executable)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dev", action="store_true", help="Build sidecar, then run the native development window"
    )
    parser.add_argument(
        "--feature", action="append", choices=["ifcopenshell", "ortools", "docling"], default=[]
    )
    args = parser.parse_args()
    try:
        command = cli_command(ROOT)
        for tool in ("pnpm", "cargo", "rustc"):
            if shutil.which(tool) is None:
                raise RuntimeError(f"Native build requires {tool}")
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/lock_dependencies.py"), "--check"],
            check=True,
            cwd=ROOT,
        )
        sidecar = [sys.executable, str(ROOT / "scripts/build_sidecar.py")]
        for feature in args.feature:
            sidecar.extend(["--feature", feature])
        subprocess.run(sidecar, check=True, cwd=ROOT)
        subprocess.run(
            [*command, "dev" if args.dev else "build", "--", "--locked"],
            check=True,
            cwd=ROOT / "desktop",
        )
        return 0
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"Desktop build failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
