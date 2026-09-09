"""Fast release/CI guard: require real lockfiles before frozen installations."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCKS = ("uv.lock", "frontend/pnpm-lock.yaml", "desktop/src-tauri/Cargo.lock")


def main() -> int:
    missing = [
        path for path in LOCKS if not (ROOT / path).is_file() or (ROOT / path).stat().st_size == 0
    ]
    if missing:
        print("BLOCKED: missing resolved dependency locks: " + ", ".join(missing), file=sys.stderr)
        print(
            (
                "Run scripts/lock_dependencies.py on a connected toolchain, "
                "review and commit the three files."
            ),
            file=sys.stderr,
        )
        return 2
    print(
        "PASS: all three lockfiles are present; frozen package "
        "managers must still validate their contents"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
