"""Tests for IIIF filesystem integration behavior."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from iiif_fsspec.exceptions import InvalidPathError
from iiif_fsspec.filesystem import IIIFFileSystem
from iiif_fsspec.iiif_file import IIIFFile
from iiif_fsspec.manifest import parse_manifest

MANIFEST_PATH = "iiif://example.org/iiif/manifest.json"
MANIFEST_URL = "https://example.org/iiif/manifest.json"
IMAGE_URL_1 = "https://images.example.org/iiif/2/abc123/full/max/0/default.jpg"


def _prime_manifest_cache(iiif_fs: IIIFFileSystem, sample_manifest_v3: dict) -> None:
    iiif_fs._manifest_cache[MANIFEST_URL] = parse_manifest(sample_manifest_v3)


def test_ls_manifest(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: dict,
) -> None:
    httpx_mock.add_response(method="GET", url=MANIFEST_URL, json=sample_manifest_v3)

    entries = iiif_fs.ls(MANIFEST_PATH, detail=True)

    assert len(entries) == 2
    assert entries[0]["name"].endswith("/canvas-one.jpg")
    assert entries[0]["type"] == "file"


def test_info_manifest(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: dict,
) -> None:
    del httpx_mock, sample_manifest_v3

    info = iiif_fs.info(MANIFEST_PATH)

    assert info["type"] == "directory"
    assert info["name"] == MANIFEST_PATH


def test_info_canvas(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: dict,
) -> None:
    del httpx_mock
    _prime_manifest_cache(iiif_fs, sample_manifest_v3)

    canvas_path = f"{MANIFEST_PATH}/canvas-one.jpg"
    info = iiif_fs.info(canvas_path)

    assert info["type"] == "file"
    assert info["iiif_label"] == "Canvas One"


def test_cat_file_full(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: dict,
) -> None:
    _prime_manifest_cache(iiif_fs, sample_manifest_v3)
    httpx_mock.add_response(method="GET", url=IMAGE_URL_1, content=b"abcdef")

    payload = iiif_fs.cat_file(f"{MANIFEST_PATH}/canvas-one.jpg")

    assert payload == b"abcdef"


def test_cat_file_range(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: dict,
) -> None:
    _prime_manifest_cache(iiif_fs, sample_manifest_v3)
    httpx_mock.add_response(
        method="GET",
        url=IMAGE_URL_1,
        content=b"cde",
        match_headers={"Range": "bytes=2-4"},
    )

    payload = iiif_fs.cat_file(f"{MANIFEST_PATH}/canvas-one.jpg", start=2, end=5)

    assert payload == b"cde"


def test_open_readonly(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: dict,
) -> None:
    _prime_manifest_cache(iiif_fs, sample_manifest_v3)
    httpx_mock.add_response(method="GET", url=IMAGE_URL_1, content=b"abc")

    with iiif_fs.open(f"{MANIFEST_PATH}/canvas-one.jpg", "rb") as handle:
        assert isinstance(handle, IIIFFile)
        assert handle.read(3) == b"abc"


def test_open_write_raises(iiif_fs: IIIFFileSystem) -> None:
    with pytest.raises(NotImplementedError):
        iiif_fs.open(f"{MANIFEST_PATH}/canvas-one.jpg", "wb")


def test_manifest_caching(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: dict,
) -> None:
    del iiif_fs
    fs = IIIFFileSystem(skip_instance_cache=True)
    httpx_mock.add_response(method="GET", url=MANIFEST_URL, json=sample_manifest_v3)

    fs.ls(MANIFEST_PATH)
    fs.ls(MANIFEST_PATH)

    manifest_requests = [req for req in httpx_mock.get_requests() if str(req.url) == MANIFEST_URL]
    assert len(manifest_requests) == 1


def test_invalid_path_raises(iiif_fs: IIIFFileSystem) -> None:
    with pytest.raises(InvalidPathError):
        iiif_fs.ls("iiif://")
