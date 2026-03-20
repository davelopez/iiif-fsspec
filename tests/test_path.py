"""Tests for IIIF path handling utilities."""

from iiif_fsspec.path import (
    make_canvas_path,
    parse_path,
    sanitize_filename,
    strip_protocol,
    to_iiif_url,
)
from iiif_fsspec.types import CanvasInfo


def test_strip_protocol_roundtrip() -> None:
    assert (
        strip_protocol("iiif://example.org/iiif/manifest.json") == "example.org/iiif/manifest.json"
    )
    assert (
        strip_protocol("https://example.org/iiif/manifest.json")
        == "https://example.org/iiif/manifest.json"
    )


def test_to_iiif_url_from_protocol_path() -> None:
    assert (
        to_iiif_url("iiif://example.org/iiif/manifest.json")
        == "https://example.org/iiif/manifest.json"
    )


def test_parse_manifest_path_without_canvas() -> None:
    manifest_url, canvas_name = parse_path("iiif://example.org/iiif/manifest.json")
    assert manifest_url == "https://example.org/iiif/manifest.json"
    assert canvas_name is None


def test_parse_manifest_path_with_canvas() -> None:
    manifest_url, canvas_name = parse_path("iiif://example.org/iiif/manifest.json/canvas-1.jpg")
    assert manifest_url == "https://example.org/iiif/manifest.json"
    assert canvas_name == "canvas-1.jpg"


def test_make_canvas_path() -> None:
    canvas = CanvasInfo(
        id="https://example.org/iiif/canvas/1",
        label="Canvas 1",
        image_url="https://example.org/image/full/max/0/default.jpg",
        service_url="https://example.org/image",
        width=1200,
        height=800,
    )
    assert make_canvas_path("iiif://example.org/iiif/manifest.json", canvas) == (
        "iiif://example.org/iiif/manifest.json/canvas-1.jpg"
    )


def test_sanitize_filename_unicode_and_specials() -> None:
    assert sanitize_filename("Folio 1r: Intro") == "folio-1r-intro"
    assert sanitize_filename("Caf\u00e9 \u2014 side A") == "cafe-side-a"


def test_parse_empty_path() -> None:
    manifest_url, canvas_name = parse_path("")
    assert manifest_url == ""
    assert canvas_name is None


def test_parse_non_manifest_two_segment_path() -> None:
    manifest_url, canvas_name = parse_path("iiif://example.org/iiif/canvas-1.jpg")
    assert manifest_url == "https://example.org/iiif"
    assert canvas_name == "canvas-1.jpg"
