"""Tests for IIIF manifest parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from iiif_fsspec.exceptions import ManifestParseError, UnsupportedVersionError
from iiif_fsspec.manifest import (
    detect_resource_kind,
    detect_version,
    parse_manifest,
    parse_resource,
)
from iiif_fsspec.types import CollectionInfo


def _load_fixture(name: str) -> dict:
    fixture_path = Path(__file__).parent / "data" / name
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_parse_valid_v2_manifest() -> None:
    data = _load_fixture("manifest_v2.json")
    manifest = parse_manifest(data)

    assert manifest.version == 2
    assert manifest.label == "Sample v2 Manifest"
    assert len(manifest.canvases) == 2
    assert manifest.canvases[0].service_url == "https://images.example.org/iiif/2/ghi789"


def test_parse_valid_v3_manifest() -> None:
    data = _load_fixture("manifest_v3.json")
    manifest = parse_manifest(data)

    assert manifest.version == 3
    assert manifest.label == "Sample v3 Manifest"
    assert len(manifest.canvases) == 2
    assert manifest.canvases[1].service_url == "https://images.example.org/iiif/2/def456"


def test_version_detection() -> None:
    assert detect_version(_load_fixture("manifest_v2.json")) == 2
    assert detect_version(_load_fixture("manifest_v3.json")) == 3


def test_malformed_manifest_raises_parse_error() -> None:
    with pytest.raises(ManifestParseError):
        parse_manifest(
            {
                "@context": "http://iiif.io/api/presentation/3/context.json",
                "type": "Manifest",
            }
        )


def test_missing_required_fields_handled() -> None:
    data = {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "id": "https://example.org/m",
        "type": "Manifest",
        "label": {"en": ["Broken but parseable"]},
        "items": [
            {
                "id": "https://example.org/canvas/1",
                "type": "Canvas",
                "label": {"en": ["No image"]},
            }
        ],
    }
    manifest = parse_manifest(data)
    assert manifest.label == "Broken but parseable"
    assert manifest.canvases == []


def test_multiple_canvases_extracted() -> None:
    manifest = parse_manifest(_load_fixture("manifest_v2.json"))
    ids = [canvas.id for canvas in manifest.canvases]
    assert ids == ["https://example.org/iiif/v2/canvas/1", "https://example.org/iiif/v2/canvas/2"]


def test_unsupported_version_error() -> None:
    with pytest.raises(UnsupportedVersionError):
        detect_version({"id": "https://example.org/no-context"})


def test_parse_valid_v2_collection_resource() -> None:
    data = _load_fixture("collection_v2.json")
    resource = parse_resource(data)

    assert isinstance(resource, CollectionInfo)
    assert resource.version == 2
    assert resource.label == "Top Collection"
    assert len(resource.members) == 2
    assert resource.members[0].kind == "collection"
    assert resource.members[1].kind == "manifest"


def test_detect_resource_kind_collection() -> None:
    assert detect_resource_kind(_load_fixture("collection_v2.json")) == "collection"


def test_parse_v3_manifest_without_top_level_type() -> None:
    manifest = parse_manifest(
        {
            "@context": "http://iiif.io/api/presentation/3/context.json",
            "id": "https://example.org/missing-type",
            "label": {"en": ["Missing Type"]},
            "items": [
                {
                    "id": "https://example.org/canvas/1",
                    "type": "Canvas",
                    "label": {"en": ["Canvas 1"]},
                    "items": [
                        {
                            "type": "AnnotationPage",
                            "items": [
                                {
                                    "type": "Annotation",
                                    "body": {
                                        "id": "https://example.org/image.jpg",
                                        "type": "Image",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )

    assert manifest.version == 3
    assert len(manifest.canvases) == 1
