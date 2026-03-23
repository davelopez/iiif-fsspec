"""Shared helpers for real-world iiif-fsspec examples."""

from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_MANIFEST_URL = "https://iiif.io/api/cookbook/recipe/0001-mvm-image/manifest.json"


# Allow running examples directly from a source checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def to_iiif_path(manifest_url: str) -> str:
    """Convert an HTTP(S) manifest URL to an iiif:// path accepted by the filesystem."""
    if manifest_url.startswith("iiif://"):
        return manifest_url
    cleaned = manifest_url.removeprefix("https://").removeprefix("http://")
    return f"iiif://{cleaned}"
