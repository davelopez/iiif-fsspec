"""Tests for IIIFFileSystem when input paths are raw https:// URLs."""

from __future__ import annotations

from typing import cast

from pytest_httpx import HTTPXMock

from iiif_fsspec.filesystem import IIIFFileSystem
from iiif_fsspec.manifest import parse_manifest
from iiif_fsspec.path import make_resource_path

from .conftest import JSONDict

MANIFEST_URL = "https://example.org/iiif/manifest.json"
MANIFEST_PATH = make_resource_path(MANIFEST_URL, kind="manifest")
OUTPUT_MANIFEST_PATH = MANIFEST_PATH.removeprefix("iiif://")
IMAGE_URL_1 = "https://images.example.org/iiif/2/abc123/full/max/0/default.jpg"


def _prime(iiif_fs: IIIFFileSystem, sample_manifest_v3: JSONDict) -> None:
    iiif_fs._manifest_cache[MANIFEST_URL] = parse_manifest(sample_manifest_v3)


def test_ls_names_are_canonical_tokenized_paths(
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _prime(iiif_fs, sample_manifest_v3)

    names = iiif_fs.ls(MANIFEST_URL, detail=False)

    assert len(names) == 2
    assert all(n.startswith(f"{OUTPUT_MANIFEST_PATH}/") for n in names), names


def test_ls_detail_names_are_canonical_tokenized_paths(
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _prime(iiif_fs, sample_manifest_v3)

    entries = iiif_fs.ls(MANIFEST_URL, detail=True)

    assert all(str(e["name"]).startswith(f"{OUTPUT_MANIFEST_PATH}/") for e in entries), entries


def test_info_manifest_returns_canonical_tokenized_path(
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _prime(iiif_fs, sample_manifest_v3)

    info = iiif_fs.info(MANIFEST_URL)

    assert info["type"] == "directory"
    assert str(info["name"]) == OUTPUT_MANIFEST_PATH


def test_info_canvas_returns_canonical_tokenized_path(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _prime(iiif_fs, sample_manifest_v3)
    httpx_mock.add_response(method="HEAD", url=IMAGE_URL_1, headers={"Content-Length": "6"})
    canvas_path = f"{MANIFEST_URL}/canvas-one.jpg"

    info = iiif_fs.info(canvas_path)

    assert info["type"] == "file"
    assert str(info["name"]) == f"{OUTPUT_MANIFEST_PATH}/canvas-one.jpg"


def test_cat_file_with_https_path(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _prime(iiif_fs, sample_manifest_v3)
    httpx_mock.add_response(method="GET", url=IMAGE_URL_1, content=b"hello")

    payload = iiif_fs.cat_file(f"{MANIFEST_URL}/canvas-one.jpg")

    assert payload == b"hello"


def test_glob_with_https_path(
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _prime(iiif_fs, sample_manifest_v3)

    matches = cast(list[str], iiif_fs.glob(f"{MANIFEST_PATH}/*"))

    assert len(matches) == 2
    assert all(m.startswith(f"{OUTPUT_MANIFEST_PATH}/") for m in matches), matches
    assert f"{OUTPUT_MANIFEST_PATH}/canvas-one.jpg" in matches


def test_glob_no_match_returns_empty(
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _prime(iiif_fs, sample_manifest_v3)

    matches = iiif_fs.glob(f"{MANIFEST_URL}/*.png")

    assert matches == []


def test_find_with_https_path(
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _prime(iiif_fs, sample_manifest_v3)

    found = iiif_fs.find(MANIFEST_URL)

    assert len(found) == 2
    assert all(p.startswith(f"{OUTPUT_MANIFEST_PATH}/") for p in found), found


def test_manifest_fetch_uses_https_url(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    """Passing an https:// path fetches the manifest at that URL, not iiif://."""
    httpx_mock.add_response(method="GET", url=MANIFEST_URL, json=sample_manifest_v3)

    names = iiif_fs.ls(MANIFEST_URL, detail=False)

    assert len(names) == 2
    assert names[0].startswith(f"{OUTPUT_MANIFEST_PATH}/")
