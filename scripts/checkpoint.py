"""Create and verify a source-only ZIP. Never treats a path as delivered storage."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".data",
    "target",
    "dist",
    "artifacts",
    "test-results",
    "playwright-report",
    "test-results-ifc",
    "playwright-report-ifc",
    ".import_linter_cache",
    ".verification-work",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = [
        p
        for p in ROOT.rglob("*")
        if p.is_file()
        and not p.is_symlink()
        and not any(part in EXCLUDED for part in p.relative_to(ROOT).parts)
        and not str(p.relative_to(ROOT)).startswith(
            ("frontend/public/viewer/", "desktop/src-tauri/binaries/")
        )
        and p.suffix not in {".pyc", ".zip", ".tsbuildinfo"}
        and not (p.name.startswith(".env") and p.name != ".env.example")
    ]
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(files):
            archive.write(path, Path(ROOT.name) / path.relative_to(ROOT))
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None, "ZIP integrity failure"
        names = archive.namelist()
        for required in [
            "pyproject.toml",
            "frontend/package.json",
            "backend/app/api/main.py",
            "backend/app/domain/models.py",
            "frontend/src/App.tsx",
            "frontend/src/api/client.ts",
            "desktop/src-tauri/src/lib.rs",
            "desktop/src-tauri/Cargo.toml",
        ]:
            assert f"{ROOT.name}/{required}" in names, required
        assert any("backend/tests/" in n and n.endswith(".py") for n in names), "Tests missing"
    manifest = {
        "archive": output.name,
        "files": len(files),
        "bytes": output.stat().st_size,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "integrity": "PASS",
        "real_source_verified": True,
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
