"""Manifest parsing for IIIF Presentation API v2 and v3."""

from __future__ import annotations

from typing import Any, Literal, TypeAlias

from iiif_fsspec.exceptions import ManifestParseError, UnsupportedVersionError
from iiif_fsspec.types import CanvasInfo, ManifestInfo, ManifestParser

V3LabelValue: TypeAlias = str | list[str] | dict[str, str | list[str]] | None
ServiceValue: TypeAlias = dict[str, object] | list[object] | None


class V3ManifestParser(ManifestParser):
    """Parser for IIIF Presentation API v3 manifests."""

    def parse(self, data: dict[str, Any]) -> ManifestInfo:
        """Parse a v3 manifest into :class:`ManifestInfo`."""
        manifest_id = str(data.get("id") or "")
        if not manifest_id:
            raise ManifestParseError("v3 manifest missing 'id'")

        label = _extract_v3_label(data.get("label"))
        canvases_raw = data.get("items")
        if not isinstance(canvases_raw, list):
            raise ManifestParseError("v3 manifest missing 'items' canvases list")

        canvases: list[CanvasInfo] = []
        for canvas in canvases_raw:
            if not isinstance(canvas, dict):
                continue
            canvas_id = str(canvas.get("id") or "")
            if not canvas_id:
                continue

            body = _v3_first_body(canvas)
            if body is None:
                continue

            image_url = str(body.get("id") or body.get("@id") or "")
            if not image_url:
                continue

            service_url = _extract_service_id(body.get("service"))
            canvas_label = _extract_v3_label(canvas.get("label"))

            canvases.append(
                CanvasInfo(
                    id=canvas_id,
                    label=canvas_label or canvas_id.rsplit("/", maxsplit=1)[-1],
                    image_url=image_url,
                    service_url=service_url,
                    width=_safe_int(canvas.get("width")),
                    height=_safe_int(canvas.get("height")),
                    format=_image_format_from_body(body),
                )
            )

        return ManifestInfo(id=manifest_id, label=label, canvases=canvases, version=3)


class V2ManifestParser(ManifestParser):
    """Parser for IIIF Presentation API v2 manifests."""

    def parse(self, data: dict[str, Any]) -> ManifestInfo:
        """Parse a v2 manifest into :class:`ManifestInfo`."""
        manifest_id = str(data.get("@id") or data.get("id") or "")
        if not manifest_id:
            raise ManifestParseError("v2 manifest missing '@id'")

        label_value = data.get("label")
        if isinstance(label_value, list) and label_value:
            label = str(label_value[0])
        else:
            label = str(label_value or "")

        sequences = data.get("sequences")
        if not isinstance(sequences, list) or not sequences:
            raise ManifestParseError("v2 manifest missing 'sequences'")
        sequence0 = sequences[0]
        if not isinstance(sequence0, dict):
            raise ManifestParseError("v2 manifest has malformed sequence")
        canvases_raw = sequence0.get("canvases")
        if not isinstance(canvases_raw, list):
            raise ManifestParseError("v2 manifest missing sequence canvases")

        canvases: list[CanvasInfo] = []
        for canvas in canvases_raw:
            if not isinstance(canvas, dict):
                continue
            canvas_id = str(canvas.get("@id") or canvas.get("id") or "")
            if not canvas_id:
                continue

            images = canvas.get("images")
            if not isinstance(images, list) or not images or not isinstance(images[0], dict):
                continue
            resource = images[0].get("resource")
            if not isinstance(resource, dict):
                continue

            image_url = str(resource.get("@id") or resource.get("id") or "")
            if not image_url:
                continue

            service_url = _extract_service_id(resource.get("service"))
            canvas_label = str(canvas.get("label") or canvas_id.rsplit("/", maxsplit=1)[-1])

            canvases.append(
                CanvasInfo(
                    id=canvas_id,
                    label=canvas_label,
                    image_url=image_url,
                    service_url=service_url,
                    width=_safe_int(canvas.get("width")),
                    height=_safe_int(canvas.get("height")),
                    format=_image_format_from_body(resource),
                )
            )

        return ManifestInfo(id=manifest_id, label=label, canvases=canvases, version=2)


def detect_version(data: dict[str, Any]) -> Literal[2, 3]:
    """Detect IIIF Presentation API version from a manifest dictionary."""
    context = data.get("@context")
    contexts = context if isinstance(context, list) else [context]
    context_text = " ".join(str(item) for item in contexts if item is not None).lower()

    if "presentation/3" in context_text:
        return 3
    if "presentation/2" in context_text:
        return 2

    if data.get("type") == "Manifest":
        return 3
    if data.get("@type") == "sc:Manifest":
        return 2

    raise UnsupportedVersionError("Could not detect supported IIIF Presentation version")


def parse_manifest(data: dict[str, Any]) -> ManifestInfo:
    """Parse a IIIF manifest with automatic version detection."""
    version = detect_version(data)
    parser: ManifestParser = V3ManifestParser() if version == 3 else V2ManifestParser()
    return parser.parse(data)


def _v3_first_body(canvas: dict[str, Any]) -> dict[str, Any] | None:
    """Get the first annotation body in a v3 canvas."""
    pages = canvas.get("items")
    if not isinstance(pages, list) or not pages:
        return None
    first_page = pages[0]
    if not isinstance(first_page, dict):
        return None
    annotations = first_page.get("items")
    if not isinstance(annotations, list) or not annotations:
        return None
    first_annotation = annotations[0]
    if not isinstance(first_annotation, dict):
        return None
    body = first_annotation.get("body")
    if isinstance(body, list):
        body = body[0] if body else None
    return body if isinstance(body, dict) else None


def _extract_v3_label(value: V3LabelValue) -> str:
    """Extract a label from v3 label object shapes."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return str(value[0]) if value else ""
    if isinstance(value, dict):
        for localized in value.values():
            if isinstance(localized, list) and localized:
                return str(localized[0])
            if isinstance(localized, str):
                return localized
    return ""


def _extract_service_id(service: ServiceValue) -> str | None:
    """Extract service ID from v2/v3 service declarations."""
    if isinstance(service, list):
        for item in service:
            if not isinstance(item, (dict, list)):
                continue
            extracted = _extract_service_id(item)
            if extracted:
                return extracted
        return None
    if isinstance(service, dict):
        candidate = service.get("id") or service.get("@id")
        return str(candidate) if candidate else None
    return None


def _image_format_from_body(body: dict[str, Any]) -> str:
    """Map body/resource format to file extension."""
    image_format = str(body.get("format") or "").lower()
    if "png" in image_format:
        return "png"
    if "tif" in image_format:
        return "tif"
    if "webp" in image_format:
        return "webp"

    image_id = str(body.get("id") or body.get("@id") or "")
    if image_id.endswith(".png"):
        return "png"
    if image_id.endswith(".tif") or image_id.endswith(".tiff"):
        return "tif"
    if image_id.endswith(".webp"):
        return "webp"
    return "jpg"


def _safe_int(value: object) -> int | None:
    """Best-effort conversion to integer."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None
