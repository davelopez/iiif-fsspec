"""Read-only file object implementation for IIIF image resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fsspec.spec import AbstractBufferedFile


class IIIFFile(AbstractBufferedFile):
    """Read-only buffered file for IIIF images."""

    def __init__(
        self,
        fs: IIIFFileSystem,
        path: str,
        mode: str = "rb",
        block_size: str = "default",
        autocommit: bool = True,
        cache_type: str = "readahead",
        cache_options: dict[str, object] | None = None,
    ) -> None:
        """Initialize a read-only IIIF file wrapper."""
        if mode != "rb":
            raise NotImplementedError("IIIF files are read-only")
        super().__init__(
            fs=fs,
            path=path,
            mode=mode,
            block_size=block_size,
            autocommit=autocommit,
            cache_type=cache_type,
            cache_options=cache_options,
        )

    def _fetch_range(self, start: int, end: int) -> bytes:
        """Fetch a byte range from the filesystem-backed canvas image."""
        payload = self.fs.cat_file(self.path, start=start, end=end)
        return bytes(payload)


if TYPE_CHECKING:
    from iiif_fsspec.filesystem import IIIFFileSystem
