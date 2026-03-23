"""Read a byte range from the first canvas in a real IIIF manifest.

Usage:
    uv run python examples/read_first_canvas.py
    uv run python examples/read_first_canvas.py --bytes 2048
"""

from __future__ import annotations

import argparse

from common import DEFAULT_MANIFEST_URL, to_iiif_path

from iiif_fsspec.filesystem import IIIFFileSystem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read bytes from first canvas image")
    parser.add_argument(
        "--manifest-url",
        default=DEFAULT_MANIFEST_URL,
        help="IIIF manifest URL (HTTP(S) or iiif://)",
    )
    parser.add_argument(
        "--bytes",
        type=int,
        default=1024,
        dest="num_bytes",
        help="Number of bytes to fetch from the beginning of the image",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = to_iiif_path(args.manifest_url)

    fs = IIIFFileSystem()
    canvas_paths = fs.ls(manifest_path, detail=False)
    if not canvas_paths:
        raise RuntimeError("Manifest contains no canvases")

    first_canvas = canvas_paths[0]
    payload = fs.cat_file(first_canvas, start=0, end=max(args.num_bytes, 1))
    chunk = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)

    print(f"Manifest : {manifest_path}")
    print(f"Canvas   : {first_canvas}")
    print(f"Bytes    : {len(chunk)}")
    print(f"Hex head : {chunk[:32].hex()}")


if __name__ == "__main__":
    main()
