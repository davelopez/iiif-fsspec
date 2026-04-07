"""Tests for IIIF path handling utilities."""

from iiif_fsspec.path import (
    canonicalize_resource_path,
    decode_collection_member_resource_url,
    decode_resource_url_token,
    encode_resource_url_token,
    is_collection_member_path,
    make_canvas_path,
    make_collection_member_path,
    make_resource_path,
    parse_path,
    sanitize_filename,
    strip_protocol,
    to_iiif_url,
)
from iiif_fsspec.types import CanvasInfo, CollectionMemberInfo

MANIFEST_URL = "https://example.org/iiif/manifest.json"
MANIFEST_TOKEN = encode_resource_url_token(MANIFEST_URL)
MANIFEST_PATH = f"iiif://manifest--{MANIFEST_TOKEN}.json"
OUTPUT_MANIFEST_PATH = f"manifest--{MANIFEST_TOKEN}.json"


def test_strip_protocol_roundtrip() -> None:
    assert strip_protocol(MANIFEST_PATH) == f"manifest--{MANIFEST_TOKEN}.json"
    assert strip_protocol(MANIFEST_URL) == MANIFEST_URL


def test_to_iiif_url_from_protocol_path() -> None:
    assert to_iiif_url(MANIFEST_PATH) == MANIFEST_URL


def test_parse_manifest_path_without_canvas() -> None:
    manifest_url, canvas_name = parse_path(MANIFEST_PATH)
    assert manifest_url == MANIFEST_URL
    assert canvas_name is None


def test_parse_manifest_path_without_protocol() -> None:
    manifest_url, canvas_name = parse_path(OUTPUT_MANIFEST_PATH)
    assert manifest_url == MANIFEST_URL
    assert canvas_name is None


def test_parse_manifest_path_with_canvas() -> None:
    manifest_url, canvas_name = parse_path(f"{MANIFEST_PATH}/canvas-1.jpg")
    assert manifest_url == MANIFEST_URL
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
    assert make_canvas_path(MANIFEST_PATH, canvas) == f"{MANIFEST_PATH}/canvas-1.jpg"


def test_sanitize_filename_unicode_and_specials() -> None:
    assert sanitize_filename("Folio 1r: Intro") == "folio-1r-intro"
    assert sanitize_filename("Caf\u00e9 \u2014 side A") == "cafe-side-a"


def test_parse_empty_path() -> None:
    manifest_url, canvas_name = parse_path("")
    assert manifest_url == ""
    assert canvas_name is None


def test_parse_non_manifest_two_segment_path() -> None:
    manifest_url, canvas_name = parse_path("iiif://example.org/iiif/canvas-1.jpg")
    assert manifest_url == ""
    assert canvas_name is None


def test_parse_collection_style_path_without_json() -> None:
    manifest_url, canvas_name = parse_path("https://example.org/iiif/collection/top")
    assert manifest_url == "https://example.org/iiif/collection/top"
    assert canvas_name is None


def test_parse_collection_style_path_with_dotted_tail_not_canvas() -> None:
    manifest_url, canvas_name = parse_path("https://example.org/iiif/collection/top.v1")
    assert manifest_url == "https://example.org/iiif/collection/top.v1"
    assert canvas_name is None


def test_parse_non_manifest_path_with_known_image_extension() -> None:
    manifest_url, canvas_name = parse_path("https://example.org/iiif/asset/page-001.webp")
    assert manifest_url == "https://example.org/iiif/asset"
    assert canvas_name == "page-001.webp"


def test_make_resource_path() -> None:
    assert make_resource_path(MANIFEST_URL, kind="manifest") == MANIFEST_PATH


def test_canonicalize_resource_path_preserves_nested_prefix() -> None:
    parent = make_resource_path("https://example.org/iiif/collection/top", kind="collection")
    member = make_collection_member_path(
        parent,
        CollectionMemberInfo(
            id=MANIFEST_URL,
            label="Book 1",
            kind="manifest",
        ),
    )
    assert canonicalize_resource_path(member, MANIFEST_URL, kind="manifest") == member


def test_parse_path_rejects_legacy_iiif_host_style() -> None:
    manifest_url, canvas_name = parse_path("iiif://example.org/iiif/manifest.json")
    assert manifest_url == ""
    assert canvas_name is None


def test_encode_decode_resource_url_token_roundtrip() -> None:
    resource_url = "https://example.org/iiif/manifest/book-1.json"
    token = encode_resource_url_token(resource_url)
    assert decode_resource_url_token(token) == resource_url


def test_decode_resource_url_token_rejects_invalid_value() -> None:
    assert decode_resource_url_token("bad$$") is None


def test_make_and_decode_collection_member_path_roundtrip() -> None:
    member = CollectionMemberInfo(
        id="https://example.org/iiif/manifest/book-1.json",
        label="Book 1",
        kind="manifest",
    )

    parent = make_resource_path("https://example.org/iiif/collection/top", kind="collection")
    path = make_collection_member_path(parent, member)

    assert "/manifest-book-1--" in path
    assert path.endswith(".json")
    assert is_collection_member_path(path)
    assert decode_collection_member_resource_url(path) == member.id


def test_decode_collection_member_resource_url_rejects_non_member_path() -> None:
    non_member = make_resource_path(
        "https://example.org/iiif/manifest/book-1.json",
        kind="manifest",
    )
    assert not is_collection_member_path(non_member)
    assert decode_collection_member_resource_url(non_member) is None
