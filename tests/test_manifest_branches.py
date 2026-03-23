"""Additional branch coverage tests for manifest parsing helpers."""

from __future__ import annotations

import pytest

from iiif_fsspec.exceptions import ManifestParseError
from iiif_fsspec.manifest import (
    _detect_member_kind,
    _extract_service_id,
    _extract_v3_label,
    _image_format_from_body,
    detect_resource_kind,
    detect_version,
    parse_manifest,
    parse_resource,
)
from iiif_fsspec.types import CollectionInfo


def test_detect_version_fallback_by_type_values() -> None:
    assert detect_version({"type": "Manifest"}) == 3
    assert detect_version({"type": "Collection"}) == 3
    assert detect_version({"@type": "sc:Manifest"}) == 2
    assert detect_version({"@type": "sc:Collection"}) == 2


def test_detect_resource_kind_fallbacks() -> None:
    assert detect_resource_kind({"type": "Manifest"}) == "manifest"
    assert detect_resource_kind({"@type": "sc:Collection"}) == "collection"
    assert detect_resource_kind({"collections": []}) == "collection"


def test_extract_v3_label_shapes() -> None:
    assert _extract_v3_label("Direct") == "Direct"
    assert _extract_v3_label(["From List"]) == "From List"
    assert _extract_v3_label({"en": ["From Dict"]}) == "From Dict"
    assert _extract_v3_label({"none": "Plain"}) == "Plain"
    assert _extract_v3_label(None) == ""


def test_extract_service_id_nested_shapes() -> None:
    service = [{"id": "https://example.org/svc"}, "ignored", {"@id": "https://example.org/alt"}]
    assert _extract_service_id(service) == "https://example.org/svc"
    assert _extract_service_id({"@id": "https://example.org/v2"}) == "https://example.org/v2"
    assert _extract_service_id(None) is None


def test_image_format_detection_variants() -> None:
    assert _image_format_from_body({"format": "image/png"}) == "png"
    assert _image_format_from_body({"format": "image/tiff"}) == "tif"
    assert _image_format_from_body({"format": "image/webp"}) == "webp"
    assert _image_format_from_body({"id": "https://example.org/a.png"}) == "png"
    assert _image_format_from_body({"@id": "https://example.org/a.tiff"}) == "tif"
    assert _image_format_from_body({}) == "jpg"


def test_parse_v2_missing_sequences_raises() -> None:
    with pytest.raises(ManifestParseError):
        parse_manifest(
            {
                "@context": "http://iiif.io/api/presentation/2/context.json",
                "@id": "https://example.org/m",
                "@type": "sc:Manifest",
                "label": "x",
            }
        )


def test_parse_v2_skips_invalid_canvas_entries() -> None:
    manifest = parse_manifest(
        {
            "@context": "http://iiif.io/api/presentation/2/context.json",
            "@id": "https://example.org/m",
            "@type": "sc:Manifest",
            "label": ["ok"],
            "sequences": [
                {"canvases": [{"@id": "https://example.org/canvas/1", "images": []}, {}]}
            ],
        }
    )
    assert manifest.version == 2
    assert manifest.canvases == []


def test_parse_v3_parses_non_numeric_dimensions_as_none() -> None:
    manifest = parse_manifest(
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "id": "https://example.org/m3",
            "type": "Manifest",
            "label": {"en": ["m3"]},
            "items": [
                {
                    "id": "https://example.org/canvas/1",
                    "type": "Canvas",
                    "label": {"en": ["c1"]},
                    "width": "NaN",
                    "height": None,
                    "items": [
                        {
                            "type": "AnnotationPage",
                            "items": [
                                {
                                    "type": "Annotation",
                                    "body": {
                                        "id": "https://example.org/image.jpg",
                                        "service": {"id": "https://example.org/service"},
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    assert len(manifest.canvases) == 1
    assert manifest.canvases[0].width is None
    assert manifest.canvases[0].height is None


def test_parse_v2_collection_members_field_supported() -> None:
    resource = parse_resource(
        {
            "@context": "http://iiif.io/api/presentation/2/context.json",
            "@id": "https://example.org/collection",
            "@type": "sc:Collection",
            "label": "root",
            "members": [
                {
                    "@id": "https://example.org/manifest/1",
                    "@type": "sc:Manifest",
                    "label": "m1",
                }
            ],
        }
    )
    assert isinstance(resource, CollectionInfo)
    assert len(resource.members) == 1
    assert resource.members[0].kind == "manifest"


def test_detect_member_kind_unknown_returns_none() -> None:
    assert _detect_member_kind({"type": "Canvas"}) is None
