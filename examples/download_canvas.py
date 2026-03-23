"""Download a canvas image from a real IIIF manifest.

Usage:
    uv run python examples/download_canvas.py
    uv run python examples/download_canvas.py --index 2 --output out.jpg
"""

from __future__ import annotations

import argparse
from pathlib import Path

from common import DEFAULT_MANIFEST_URL, to_iiif_path

from iiif_fsspec.filesystem import IIIFFileSystem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download one canvas image")
    parser.add_argument(
        "--manifest-url",
        default=DEFAULT_MANIFEST_URL,
        help="IIIF manifest URL (HTTP(S) or iiif://)",
    )
    parser.add_argument(
        "--index",
        type=int,
        default=1,
        help="1-based index of canvas to download",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("downloaded_canvas.jpg"),
        help="Output file path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = to_iiif_path(args.manifest_url)

    fs = IIIFFileSystem()
    entries = fs.ls(manifest_path, detail=True)
    if not entries:
        raise RuntimeError("Manifest contains no canvases")

    if args.index < 1 or args.index > len(entries):
        raise ValueError(f"--index must be in 1..{len(entries)}")

    entry = entries[args.index - 1]
    canvas_path = str(entry["name"])

    with fs.open(canvas_path, "rb") as handle:
        payload = handle.read()

    args.output.write_bytes(payload)

    print(f"Manifest : {manifest_path}")
    print(f"Canvas   : {canvas_path}")
    print(f"Label    : {entry.get('iiif_label', '')}")
    print(f"Saved    : {args.output.resolve()}")
    print(f"Bytes    : {len(payload)}")


if __name__ == "__main__":
    main()
