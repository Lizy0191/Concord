"""Resolve real package-manager lockfiles as one recoverable change.

No lockfile is fabricated. All three tools must exist before any write. If one
resolution fails, the previous lockfile set is restored. Use --check in releases.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCKFILES = (Path("uv.lock"), Path("frontend/pnpm-lock.yaml"), Path("desktop/src-tauri/Cargo.lock"))


def normalized_newlines(content: bytes) -> bytes:
    """Compare text lockfiles independently of the platform newline convention."""
    return content.replace(b"\r\n", b"\n")


def substantively_changed_lockfiles(
    root: Path, backups: dict[Path, bytes | None]
) -> list[Path]:
    return [
        path
        for path, before in backups.items()
        if before is None
        or normalized_newlines((root / path).read_bytes()) != normalized_newlines(before)
    ]


def tools() -> dict[str, str]:
    found = {name: shutil.which(name) for name in ("uv", "pnpm", "cargo")}
    missing = [name for name, executable in found.items() if executable is None]
    if missing:
        raise RuntimeError("Required package managers are missing: " + ", ".join(missing))
    return {name: str(executable) for name, executable in found.items()}


def resolve(root: Path, *, check: bool = False) -> None:
    if check:
        missing = [str(path) for path in LOCKFILES if not (root / path).is_file()]
        if missing:
            raise RuntimeError(
                "Real lockfiles must be generated and committed: " + ", ".join(missing)
            )
    binaries = tools()
    commands = [
        [binaries["uv"], "lock", *(["--check"] if check else [])],
        [
            binaries["pnpm"],
            "--dir",
            "frontend",
            "install",
            "--lockfile-only",
            "--ignore-scripts",
            *(["--frozen-lockfile"] if check else ["--no-frozen-lockfile"]),
        ],
        [
            binaries["cargo"],
            "metadata",
            "--manifest-path",
            "desktop/src-tauri/Cargo.toml",
            "--format-version",
            "1",
            "--no-deps",
            "--locked",
        ]
        if check
        else [
            binaries["cargo"],
            "generate-lockfile",
            "--manifest-path",
            "desktop/src-tauri/Cargo.toml",
        ],
    ]
    backups = {
        path: (root / path).read_bytes() if (root / path).exists() else None for path in LOCKFILES
    }
    try:
        for command in commands:
            print("Running: " + " ".join(command), flush=True)
            subprocess.run(command, cwd=root, check=True, timeout=600)
        for path in LOCKFILES:
            if not (root / path).is_file() or (root / path).stat().st_size == 0:
                raise RuntimeError(f"Package manager did not produce a nonempty {path}")
        if check:
            changed = substantively_changed_lockfiles(root, backups)
            if changed:
                raise RuntimeError(
                    "A frozen check changed committed lockfile(s): "
                    + ", ".join(str(path) for path in changed)
                )
            # Keep the working tree byte-for-byte clean when a tool rewrites only line endings.
            for path, before in backups.items():
                if before is not None and (root / path).read_bytes() != before:
                    (root / path).write_bytes(before)
    except BaseException:
        for path, content in backups.items():
            if content is None:
                (root / path).unlink(missing_ok=True)
            else:
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_bytes(content)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Require an unchanged existing lockfile set"
    )
    args = parser.parse_args()
    try:
        resolve(ROOT, check=args.check)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(
        "PASS: real dependency lockfiles "
        + ("checked" if args.check else "generated; review and commit all three")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
