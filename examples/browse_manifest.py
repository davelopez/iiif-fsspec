"""Browse a real IIIF manifest as a virtual directory.

Usage:
    uv run python examples/browse_manifest.py
    uv run python examples/browse_manifest.py --limit 20
    uv run python examples/browse_manifest.py --manifest-url https://.../manifest.json
"""

from __future__ import annotations

import argparse

from common import DEFAULT_MANIFEST_URL, to_iiif_path

from iiif_fsspec.filesystem import IIIFFileSystem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List canvases from a IIIF manifest")
    parser.add_argument(
        "--manifest-url",
        default=DEFAULT_MANIFEST_URL,
        help="IIIF manifest URL (HTTP(S) or iiif://)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="How many canvases to print",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = to_iiif_path(args.manifest_url)

    fs = IIIFFileSystem()
    manifest_info = fs.info(manifest_path)
    entries = fs.ls(manifest_path, detail=True)

    print(f"Manifest path: {manifest_path}")
    print(f"Manifest URL : {manifest_info.get('iiif_manifest', 'unknown')}")
    print(f"Canvases     : {len(entries)}")
    print()

    for idx, entry in enumerate(entries[: args.limit], start=1):
        print(
            f"{idx:02d}. {entry['name']} | "
            f"label={entry.get('iiif_label', '')!r} | "
            f"size~={entry.get('size', 0)} | "
            f"dims={entry.get('width', '?')}x{entry.get('height', '?')}"
        )


if __name__ == "__main__":
    main()
