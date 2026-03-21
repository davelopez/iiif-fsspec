"""fsspec AsyncFileSystem implementation for IIIF manifests and images."""

from __future__ import annotations

import os
import re
from typing import cast

from fsspec.asyn import AsyncFileSystem
from fsspec.spec import AbstractBufferedFile
from fsspec.utils import glob_translate

from iiif_fsspec.client import AsyncIIIFClient
from iiif_fsspec.exceptions import InvalidPathError
from iiif_fsspec.iiif_file import IIIFFile
from iiif_fsspec.manifest import parse_manifest
from iiif_fsspec.path import make_canvas_path, parse_path, sanitize_filename, strip_protocol
from iiif_fsspec.types import CanvasInfo, IIIFEntryInfo, ManifestInfo


class IIIFFileSystem(AsyncFileSystem):
    """fsspec filesystem for IIIF resources.

    Exposes IIIF manifests as directories and canvas images as files.
    """

    protocol = "iiif"

    def __init__(
        self,
        *,
        asynchronous: bool = False,
        loop: object = None,
        timeout: float = 30.0,
        **storage_options: object,
    ) -> None:
        """Initialize the IIIF filesystem."""
        super().__init__(asynchronous=asynchronous, loop=loop, **storage_options)
        self._client = AsyncIIIFClient(timeout=timeout)
        self._manifest_cache: dict[str, ManifestInfo] = {}

    @classmethod
    def _strip_protocol(cls, path: str) -> str:
        """Strip ``iiif://`` protocol from a path."""
        return strip_protocol(path)

    async def _info(self, path: str, **kwargs: object) -> IIIFEntryInfo:
        """Return information about a manifest directory or canvas image."""
        del kwargs
        manifest_url, canvas_name = parse_path(path)
        if not manifest_url:
            raise InvalidPathError(f"Invalid IIIF path: {path}")

        if canvas_name is None:
            return IIIFEntryInfo(
                {
                    "name": _ensure_protocol_path(path),
                    "size": 0,
                    "type": "directory",
                    "iiif_manifest": manifest_url,
                }
            )

        manifest = await self._get_manifest(manifest_url)
        canvas = _find_canvas_by_filename(manifest, canvas_name)
        if canvas is None:
            raise InvalidPathError(f"Canvas not found for path: {path}")

        image_url = _canvas_image_url(canvas)
        exact_size = await self._client.get_size(image_url)
        return _canvas_entry(_ensure_protocol_path(path), canvas, size=exact_size)

    async def _ls(
        self,
        path: str,
        detail: bool = True,
        **kwargs: object,
    ) -> list[IIIFEntryInfo] | list[str]:
        """List canvases under a manifest path."""
        del kwargs
        manifest_url, canvas_name = parse_path(path)
        if not manifest_url:
            raise InvalidPathError(f"Invalid IIIF path: {path}")

        if canvas_name is not None:
            info = await self._info(path)
            if detail:
                return [info]
            return [str(info["name"])]

        manifest = await self._get_manifest(manifest_url)
        manifest_path = _ensure_protocol_path(path)

        entries: list[IIIFEntryInfo] = []
        for canvas in manifest.canvases:
            canvas_path = make_canvas_path(manifest_path, canvas)
            entries.append(_canvas_entry(canvas_path, canvas))

        if detail:
            return entries
        return [str(entry["name"]) for entry in entries]

    async def _cat_file(
        self,
        path: str,
        start: int | None = None,
        end: int | None = None,
        **kwargs: object,
    ) -> bytes:
        """Read bytes from a canvas image."""
        del kwargs
        manifest_url, canvas_name = parse_path(path)
        if not manifest_url or canvas_name is None:
            raise InvalidPathError(f"Path does not resolve to canvas image: {path}")

        manifest = await self._get_manifest(manifest_url)
        canvas = _find_canvas_by_filename(manifest, canvas_name)
        if canvas is None:
            raise InvalidPathError(f"Canvas not found for path: {path}")

        image_url = _canvas_image_url(canvas)
        return await self._client.get_bytes(image_url, start=start, end=end)

    async def _glob(
        self,
        path: str,
        maxdepth: int | None = None,
        **kwargs: object,
    ) -> list[str] | dict[str, IIIFEntryInfo]:
        """Find files by glob-matching while normalizing IIIF protocol paths."""
        if maxdepth is not None and maxdepth < 1:
            raise ValueError("maxdepth must be at least 1")

        detail = bool(kwargs.pop("detail", False))
        ends_with_slash = path.endswith("/")
        stripped_pattern = self._strip_protocol(path)

        has_magic = any(token in stripped_pattern for token in ("*", "?", "["))
        if not has_magic:
            if await self._exists(path, **kwargs):
                if detail:
                    info = await self._info(path, **kwargs)
                    return {str(info["name"]): info}
                return [path]
            return {} if detail else []

        idx_star = stripped_pattern.find("*") if "*" in stripped_pattern else len(stripped_pattern)
        idx_qmark = stripped_pattern.find("?") if "?" in stripped_pattern else len(stripped_pattern)
        idx_brace = stripped_pattern.find("[") if "[" in stripped_pattern else len(stripped_pattern)
        min_idx = min(idx_star, idx_qmark, idx_brace)

        if "/" in stripped_pattern[:min_idx]:
            min_idx = stripped_pattern[:min_idx].rindex("/")
            root = stripped_pattern[: min_idx + 1]
            depth = stripped_pattern[min_idx + 1 :].count("/") + 1
        else:
            root = ""
            depth = stripped_pattern[min_idx + 1 :].count("/") + 1

        if "**" in stripped_pattern:
            if maxdepth is not None:
                idx_double_stars = stripped_pattern.find("**")
                depth_double_stars = stripped_pattern[idx_double_stars:].count("/") + 1
                depth = depth - depth_double_stars + maxdepth
            else:
                depth = None

        allpaths = await self._find(root, maxdepth=depth, withdirs=True, detail=True, **kwargs)

        pattern = re.compile(glob_translate(stripped_pattern + ("/" if ends_with_slash else "")))
        out: dict[str, IIIFEntryInfo] = {}
        for candidate_path, info in sorted(allpaths.items()):
            normalized = strip_protocol(candidate_path)
            suffix = "/" if ends_with_slash and info["type"] == "directory" else ""
            if pattern.match(normalized + suffix):
                out[candidate_path] = info

        if detail:
            return out
        return list(out)

    async def _get_file(self, rpath: str, lpath: str, **kwargs: object) -> None:
        """Copy a single canvas file to a local path."""
        del kwargs
        if await self._isdir(rpath):
            os.makedirs(lpath, exist_ok=True)
            return

        data = await self._cat_file(rpath)
        parent = os.path.dirname(lpath)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(lpath, "wb") as handle:
            handle.write(data)

    def _open(
        self,
        path: str,
        mode: str = "rb",
        block_size: object | None = None,
        autocommit: bool = True,
        cache_options: dict[str, object] | None = None,
        **kwargs: object,
    ) -> AbstractBufferedFile:
        """Open a read-only IIIF canvas file."""
        if mode != "rb":
            raise NotImplementedError("IIIF filesystem is read-only")
        resolved_block_size = "default" if block_size is None else str(block_size)
        cache_type = kwargs.get("cache_type", "readahead")
        if not isinstance(cache_type, str):
            cache_type = "readahead"
        return IIIFFile(
            self,
            path,
            mode=mode,
            block_size=resolved_block_size,
            autocommit=autocommit,
            cache_type=cache_type,
            cache_options=cache_options,
        )

    async def _close(self) -> None:
        """Close resources held by the filesystem."""
        await self._client.close()

    async def _get_manifest(self, manifest_url: str) -> ManifestInfo:
        """Fetch and cache parsed manifest metadata."""
        cached = self._manifest_cache.get(manifest_url)
        if cached is not None:
            return cached

        manifest_json = await self._client.get_json(manifest_url)
        manifest = parse_manifest(manifest_json)
        self._manifest_cache[manifest_url] = manifest
        return manifest


def _ensure_protocol_path(path: str) -> str:
    """Ensure a path includes the ``iiif://`` protocol prefix."""
    return path if path.startswith("iiif://") else f"iiif://{strip_protocol(path)}"


def _canvas_filename(canvas: CanvasInfo) -> str:
    """Get deterministic filename for a canvas."""
    return f"{sanitize_filename(canvas.label)}.{canvas.format}"


def _find_canvas_by_filename(manifest: ManifestInfo, canvas_name: str) -> CanvasInfo | None:
    """Locate a canvas in a manifest by generated filename."""
    for canvas in manifest.canvases:
        if _canvas_filename(canvas) == canvas_name:
            return canvas
    return None


def _canvas_image_url(canvas: CanvasInfo) -> str:
    """Build canonical full-resolution image URL for a canvas."""
    if canvas.service_url:
        return f"{canvas.service_url.rstrip('/')}/full/max/0/default.jpg"
    return canvas.image_url


def _canvas_entry(path: str, canvas: CanvasInfo, *, size: int | None = None) -> IIIFEntryInfo:
    """Convert canvas metadata into fsspec-compatible entry info."""
    estimated_size = 0
    if canvas.width is not None and canvas.height is not None:
        estimated_size = max(canvas.width * canvas.height, 1)

    resolved_size = size if size is not None else estimated_size

    return IIIFEntryInfo(
        cast(
            dict[str, object],
            {
                "name": path,
                "size": resolved_size,
                "type": "file",
                "iiif_id": canvas.id,
                "iiif_label": canvas.label,
                "width": canvas.width,
                "height": canvas.height,
                "mimetype": f"image/{canvas.format}",
                "estimated_size": estimated_size,
            },
        )
    )
