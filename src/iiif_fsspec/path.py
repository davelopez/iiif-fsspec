"""Path utilities for mapping fsspec IIIF paths to canonical IIIF URLs."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from iiif_fsspec.types import CanvasInfo

_PROTOCOL = "iiif://"
_CANVAS_EXTENSIONS = {"jpg", "jpeg", "png", "tif", "tiff", "webp"}


def strip_protocol(path: str) -> str:
    """Strip the ``iiif://`` protocol prefix from a path.

    Args:
        path: fsspec path that may include the IIIF protocol.

    Returns:
        Path without the ``iiif://`` prefix.
    """
    if path.startswith(_PROTOCOL):
        return path[len(_PROTOCOL) :]
    return path


def to_iiif_url(path: str) -> str:
    """Convert a fsspec IIIF path into an HTTPS URL.

    Args:
        path: fsspec path with or without ``iiif://``.

    Returns:
        Canonical URL string.
    """
    stripped = strip_protocol(path).strip()
    if not stripped:
        return ""
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", stripped):
        return stripped
    return f"https://{stripped}"


def parse_path(path: str) -> tuple[str, str | None]:
    """Split a path into ``(manifest_url, canvas_name)``.

    When the path points to a manifest directly, ``canvas_name`` is ``None``.

    Args:
        path: fsspec IIIF path.

    Returns:
        A tuple of the manifest URL and optional canvas file name.
    """
    url = to_iiif_url(path)
    split = urlsplit(url)
    if not split.netloc:
        return "", None

    parts = [part for part in split.path.split("/") if part]
    if not parts:
        return urlunsplit((split.scheme, split.netloc, "", split.query, split.fragment)), None

    manifest_idx = next(
        (idx for idx in range(len(parts) - 1, -1, -1) if parts[idx].lower().endswith(".json")),
        None,
    )

    canvas_name: str | None = None
    if manifest_idx is None:
        if len(parts) == 1:
            manifest_parts = parts
        else:
            last_part = parts[-1]
            if _looks_like_canvas_filename(last_part):
                manifest_parts = parts[:-1]
                canvas_name = last_part
            else:
                manifest_parts = parts
    elif manifest_idx == len(parts) - 1:
        manifest_parts = parts
    else:
        manifest_parts = parts[: manifest_idx + 1]
        canvas_name = parts[manifest_idx + 1]

    manifest_path = "/" + "/".join(manifest_parts) if manifest_parts else ""
    manifest_url = urlunsplit(
        (split.scheme, split.netloc, manifest_path, split.query, split.fragment)
    )
    return manifest_url, canvas_name


def _looks_like_canvas_filename(segment: str) -> bool:
    """Return True when the final segment appears to be an image filename."""
    if "." not in segment:
        return False
    extension = segment.rsplit(".", maxsplit=1)[-1].lower()
    return extension in _CANVAS_EXTENSIONS


def sanitize_filename(name: str) -> str:
    """Convert text to a filesystem-safe filename fragment.

    Args:
        name: Source text, usually a canvas label.

    Returns:
        Safe filename fragment (without extension).
    """
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_name.lower().strip()
    lowered = re.sub(r"\s+", "-", lowered)
    lowered = re.sub(r"[^a-z0-9._-]", "-", lowered)
    lowered = re.sub(r"-+", "-", lowered).strip("-._")
    return lowered or "canvas"


def make_canvas_path(manifest_path: str, canvas: CanvasInfo) -> str:
    """Build a fsspec canvas path for a manifest and canvas.

    Args:
        manifest_path: Manifest path as fsspec-style path.
        canvas: Parsed canvas metadata.

    Returns:
        Canvas file path below the manifest directory.
    """
    base = manifest_path.rstrip("/")
    stem = sanitize_filename(canvas.label or canvas.id.rsplit("/", maxsplit=1)[-1])
    extension = canvas.format.lstrip(".") or "jpg"
    return f"{base}/{stem}.{extension}"
