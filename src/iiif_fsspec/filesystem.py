"""fsspec AsyncFileSystem implementation for IIIF manifests and images."""

from __future__ import annotations

import os
from typing import cast

from fsspec.asyn import AsyncFileSystem
from fsspec.spec import AbstractBufferedFile

from iiif_fsspec.client import AsyncIIIFClient
from iiif_fsspec.exceptions import InvalidPathError
from iiif_fsspec.iiif_file import IIIFFile
from iiif_fsspec.manifest import parse_resource
from iiif_fsspec.path import (
    decode_collection_member_resource_url,
    is_collection_member_path,
    make_canvas_path,
    make_collection_member_path,
    parse_path,
    resource_rooted_output_path,
    sanitize_filename,
    strip_protocol,
)
from iiif_fsspec.types import (
    CanvasInfo,
    CollectionInfo,
    CollectionMemberInfo,
    IIIFEntryInfo,
    ManifestInfo,
    ResourceInfo,
)


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
        headers: dict[str, str] | None = None,
        user_agent: str | None = None,
        **storage_options: object,
    ) -> None:
        """Initialize the IIIF filesystem."""
        super().__init__(asynchronous=asynchronous, loop=loop, **storage_options)
        resolved_headers = dict(headers or {})
        if user_agent and "User-Agent" not in resolved_headers:
            resolved_headers["User-Agent"] = user_agent
        self._client = AsyncIIIFClient(timeout=timeout, headers=resolved_headers)
        self._manifest_cache: dict[str, ManifestInfo] = {}
        self._resource_cache: dict[str, ResourceInfo] = {}

    @classmethod
    def _strip_protocol(cls, path: str) -> str:
        """Normalize iiif paths to protocol-free tokenized form for fsspec matching."""
        return strip_protocol(path)

    async def _info(self, path: str, **kwargs: object) -> IIIFEntryInfo:
        """Return information about a manifest directory or canvas image."""
        del kwargs
        manifest_url, canvas_name = parse_path(path)
        if not manifest_url:
            raise InvalidPathError(f"Invalid IIIF path: {path}")

        if canvas_name is None:
            resource = await self._get_resource(manifest_url)
            kind = "collection" if isinstance(resource, CollectionInfo) else "manifest"
            canonical_name = resource_rooted_output_path(path, manifest_url, kind=kind)
            return IIIFEntryInfo(
                {
                    "name": canonical_name,
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
        manifest_path = resource_rooted_output_path(path, manifest_url, kind="manifest")
        canvas_path = make_canvas_path(manifest_path, canvas)
        return _canvas_entry(canvas_path, canvas, size=exact_size)

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

        resource = await self._get_resource(manifest_url)
        if isinstance(resource, CollectionInfo):
            collection_path = resource_rooted_output_path(path, manifest_url, kind="collection")
            entries: list[IIIFEntryInfo] = []
            for member in resource.members:
                member_path = make_collection_member_path(collection_path, member)
                entries.append(_collection_member_entry(member_path, member.id, member))
        else:
            manifest_path = resource_rooted_output_path(path, manifest_url, kind="manifest")
            entries = []
            for canvas in resource.canvases:
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

        resource = await self._get_resource(manifest_url)
        if isinstance(resource, CollectionInfo):
            raise InvalidPathError(f"Path does not resolve to manifest resource: {manifest_url}")

        self._manifest_cache[manifest_url] = resource
        return resource

    async def _get_resource(self, resource_url: str) -> ResourceInfo:
        """Fetch and cache parsed IIIF resources (manifest or collection)."""
        decoded_url = decode_collection_member_resource_url(resource_url)
        if decoded_url is None and is_collection_member_path(resource_url):
            raise InvalidPathError(f"Invalid stateless collection member path: {resource_url}")

        parsed_url, _canvas_name = parse_path(resource_url)
        resolved_url = decoded_url or parsed_url or resource_url

        cached = self._resource_cache.get(resolved_url)
        if cached is not None:
            self._resource_cache[resource_url] = cached
            return cached

        manifest_cached = self._manifest_cache.get(resolved_url)
        if manifest_cached is not None:
            self._resource_cache[resource_url] = manifest_cached
            return manifest_cached

        payload = await self._client.get_json(resolved_url)
        resource = parse_resource(payload)
        self._resource_cache[resolved_url] = resource
        self._resource_cache[resource_url] = resource
        if isinstance(resource, ManifestInfo):
            self._manifest_cache[resolved_url] = resource
            self._manifest_cache[resource_url] = resource
        return resource


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


def _collection_member_entry(
    path: str,
    member_id: str,
    member: CollectionMemberInfo,
) -> IIIFEntryInfo:
    """Convert collection member metadata into a directory entry."""
    entry: dict[str, object] = {
        "name": path,
        "size": 0,
        "type": "directory",
        "iiif_id": member_id,
    }

    entry["iiif_label"] = member.label
    entry["iiif_resource_type"] = member.kind

    return IIIFEntryInfo(entry)
