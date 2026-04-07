"""Path utilities for mapping fsspec IIIF paths to canonical IIIF URLs."""

from __future__ import annotations

import base64
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from iiif_fsspec.types import CanvasInfo, CollectionMemberInfo

_PROTOCOL = "iiif://"
_CANVAS_EXTENSIONS = {"jpg", "jpeg", "png", "tif", "tiff", "webp"}
_RESOURCE_SEGMENT = re.compile(
    r"^(?P<prefix>(?:manifest|collection|resource)(?:-[A-Za-z0-9._-]+)?)--(?P<token>[A-Za-z0-9_-]+)\.json$"
)


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

    if path.startswith(_PROTOCOL):
        resource_url, canvas_name = parse_path(path)
        if resource_url:
            if canvas_name:
                return f"{resource_url.rstrip('/')}/{canvas_name}"
            return resource_url
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
    normalized = path.strip()
    if not normalized:
        return "", None

    if normalized.startswith(("https://", "http://")):
        return _parse_http_path(normalized)

    return _parse_tokenized_path(normalized)


def make_resource_path(resource_url: str, *, kind: str = "resource") -> str:
    """Build canonical stateless path for a IIIF resource URL."""
    normalized_url = resource_url.strip()
    if not normalized_url:
        return ""

    if not re.match(r"^https?://", normalized_url):
        normalized_url = f"https://{normalized_url.removeprefix(_PROTOCOL)}"

    normalized_kind = kind.lower()
    if normalized_kind not in {"manifest", "collection", "resource"}:
        normalized_kind = "resource"

    token = encode_resource_url_token(normalized_url)
    return f"{_PROTOCOL}{normalized_kind}--{token}.json"


def canonicalize_resource_path(path: str, resource_url: str, *, kind: str = "resource") -> str:
    """Return canonical iiif:// resource directory path, preserving nested stateless parents."""
    if path.startswith(_PROTOCOL):
        bare = strip_protocol(path).strip().strip("/")
        parts = [p for p in bare.split("/") if p]
        idx = _find_resource_segment(parts)
        if idx is not None and _decode_resource_segment(parts[idx]) is not None:
            return f"{_PROTOCOL}{'/'.join(parts[:idx + 1])}"
    return make_resource_path(resource_url, kind=kind)


def resource_rooted_output_path(path: str, resource_url: str, *, kind: str = "resource") -> str:
    """Return protocol-free output name for the last tokenized resource segment."""
    canonical = canonicalize_resource_path(path, resource_url, kind=kind)
    return strip_protocol(canonical).rsplit("/", maxsplit=1)[-1]


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


def encode_resource_url_token(resource_url: str) -> str:
    """Encode a resource URL to a URL-safe token without padding."""
    payload = resource_url.encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_resource_url_token(token: str) -> str | None:
    """Decode a URL-safe token into its resource URL.

    Returns ``None`` for malformed tokens.
    """
    if not token or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        return None

    padding = "=" * (-len(token) % 4)
    try:
        decoded = base64.urlsafe_b64decode(f"{token}{padding}")
        return decoded.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def make_collection_member_path(parent_path: str, member: CollectionMemberInfo) -> str:
    """Build a label-first stateless child path for collection members."""
    slug_source = member.label or member.id.rsplit("/", maxsplit=1)[-1]
    slug = sanitize_filename(slug_source)
    token = encode_resource_url_token(member.id)
    filename = f"{member.kind}-{slug}--{token}.json"
    return f"{parent_path.rstrip('/')}/{filename}"


def is_collection_member_path(path: str) -> bool:
    """Return whether a path matches the stateless collection member shape."""
    basename = _path_basename(path)
    if not basename.endswith(".json"):
        return False

    stem = basename[:-5]
    if "--" not in stem:
        return False

    prefix, _token = stem.rsplit("--", maxsplit=1)
    return prefix.startswith("manifest-") or prefix.startswith("collection-")


def decode_collection_member_resource_url(path: str) -> str | None:
    """Extract and decode collection member URL from a stateless child path."""
    basename = _path_basename(path)

    if not basename.endswith(".json"):
        return None

    stem = basename[:-5]
    if "--" not in stem:
        return None

    prefix, token = stem.rsplit("--", maxsplit=1)
    if not token or not prefix:
        return None

    if not (prefix.startswith("manifest-") or prefix.startswith("collection-")):
        return None

    return decode_resource_url_token(token)


def _parse_http_path(path: str) -> tuple[str, str | None]:
    split = urlsplit(path)
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


def _parse_tokenized_path(path: str) -> tuple[str, str | None]:
    stripped = strip_protocol(path).strip().strip("/")
    if not stripped:
        return "", None

    parts = [part for part in stripped.split("/") if part]
    resource_idx = _find_resource_segment(parts)
    if resource_idx is None:
        return "", None

    resource_url = _decode_resource_segment(parts[resource_idx])
    if resource_url is None:
        return "", None

    trailing = parts[resource_idx + 1 :]
    if not trailing:
        return resource_url, None
    if len(trailing) > 1:
        return "", None

    tail = trailing[0]
    if _looks_like_resource_segment(tail):
        return "", None

    return resource_url, tail


def _find_resource_segment(parts: list[str]) -> int | None:
    for idx in range(len(parts) - 1, -1, -1):
        if _looks_like_resource_segment(parts[idx]):
            return idx
    return None


def _looks_like_resource_segment(segment: str) -> bool:
    return _RESOURCE_SEGMENT.fullmatch(segment) is not None


def _decode_resource_segment(segment: str) -> str | None:
    match = _RESOURCE_SEGMENT.fullmatch(segment)
    if match is None:
        return None
    return decode_resource_url_token(match.group("token"))


def _path_basename(path: str) -> str:
    if path.startswith(_PROTOCOL) or not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", path):
        stripped = strip_protocol(path).rstrip("/")
        return stripped.rsplit("/", maxsplit=1)[-1] if stripped else ""
    return urlsplit(path).path.rsplit("/", maxsplit=1)[-1]
