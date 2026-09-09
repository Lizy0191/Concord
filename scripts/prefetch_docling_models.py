"""Download only public layout/table model weights, before offline PDF verification.

This is explicit development/CI setup, not document processing or live verification.
No project document or credential is read. Package versions come from uv.lock;
Docling selects its own compatible public model revisions.
"""

import argparse
import json
from pathlib import Path


def prefetch(destination: Path) -> dict:
    from docling.utils.model_downloader import download_models

    destination.mkdir(parents=True, exist_ok=True)
    download_models(
        output_dir=destination,
        with_layout=True,
        with_tableformer=True,
        with_code_formula=False,
        with_picture_classifier=False,
        with_rapidocr=False,
        with_easyocr=False,
        progress=True,
    )
    files = [path for path in destination.rglob("*") if path.is_file()]
    if not files or not any(
        path.suffix in {".bin", ".safetensors", ".pt", ".pth", ".onnx"} for path in files
    ):
        raise RuntimeError("Model setup produced no identifiable weight files")
    return {
        "status": "PREFETCHED_NOT_VERIFIED",
        "files": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "directory": str(destination.resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = prefetch(args.output.resolve())
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
