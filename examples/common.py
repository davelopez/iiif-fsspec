"""Shared helpers for real-world iiif-fsspec examples."""

from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_MANIFEST_URL = "https://api.irht.cnrs.fr/ark:/63955/fbkub82u5bw7/manifest.json"


# Allow running examples directly from a source checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from iiif_fsspec import IIIFFileSystem  # noqa: E402


def to_iiif_path(manifest_url: str) -> str:
    """Convert an HTTP(S) manifest URL to an iiif:// path accepted by the filesystem."""
    if manifest_url.startswith("iiif://"):
        return manifest_url
    cleaned = manifest_url.removeprefix("https://").removeprefix("http://")
    return f"iiif://{cleaned}"


def create_fs(timeout: float = 60.0) -> IIIFFileSystem:
    """Create a filesystem instance with a slightly larger timeout for remote demos."""
    return IIIFFileSystem(timeout=timeout)
