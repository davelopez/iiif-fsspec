"""fsspec AsyncFileSystem implementation for IIIF manifests and images."""

from __future__ import annotations

import os
from typing import cast

from fsspec.asyn import AsyncFileSystem
from fsspec.spec import AbstractBufferedFile

from iiif_fsspec.client import AsyncIIIFClient
from iiif_fsspec.exceptions import InvalidPathError
from iiif_fsspec.iiif_file import IIIFFile
from iiif_fsspec.manifest import parse_manifest
from iiif_fsspec.path import make_canvas_path, parse_path, sanitize_filename
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
        """Return path unchanged so base fsspec methods match full input style."""
        return path

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
    """Ensure a path has a protocol prefix, preserving ``https://`` / ``http://`` or defaulting to ``iiif://``."""
    if path.startswith(("iiif://", "https://", "http://")):
        return path
    return f"iiif://{path}"


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
