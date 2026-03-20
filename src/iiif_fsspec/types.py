"""Type definitions for the IIIF fsspec plugin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(slots=True)
class CanvasInfo:
    """Information about a IIIF canvas and its primary image."""

    id: str
    label: str
    image_url: str
    service_url: str | None
    width: int | None
    height: int | None
    format: str = "jpg"


@dataclass(slots=True)
class ManifestInfo:
    """Parsed IIIF manifest metadata."""

    id: str
    label: str
    canvases: list[CanvasInfo]
    version: Literal[2, 3]


class ManifestParser(Protocol):
    """Protocol for IIIF manifest parsers."""

    def parse(self, data: dict[str, Any]) -> ManifestInfo:
        """Parse a manifest dictionary into structured metadata."""
        ...


class IIIFEntryInfo(dict[str, Any]):
    """fsspec-compatible file info dictionary.

    Required keys: name, size, type
    IIIF-specific optional keys: iiif_id, iiif_label, width, height, mimetype
    """
