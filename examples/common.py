"""Shared helpers for real-world iiif-fsspec examples."""

from __future__ import annotations

import sys
from pathlib import Path

from iiif_fsspec.path import make_resource_path, parse_path

DEFAULT_MANIFEST_URL = "https://iiif.io/api/cookbook/recipe/0001-mvm-image/manifest.json"


# Allow running examples directly from a source checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def to_iiif_path(manifest_url: str) -> str:
    """Convert a manifest URL or canonical iiif path into canonical tokenized iiif path."""
    if manifest_url.startswith("iiif://"):
        parsed_url, canvas_name = parse_path(manifest_url)
        if parsed_url and canvas_name is None:
            return manifest_url
        legacy = manifest_url.removeprefix("iiif://")
        return make_resource_path(f"https://{legacy}", kind="manifest")
    return make_resource_path(manifest_url, kind="manifest")
