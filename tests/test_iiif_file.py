"""Tests for the IIIF read-only buffered file object."""

from __future__ import annotations

import re

import httpx
import pytest
from pytest_httpx import HTTPXMock

from iiif_fsspec.filesystem import IIIFFileSystem

from .conftest import JSONDict

pytestmark = pytest.mark.httpx_mock(assert_all_responses_were_requested=False)

MANIFEST_PATH = "iiif://example.org/iiif/manifest.json"
MANIFEST_URL = "https://example.org/iiif/manifest.json"
IMAGE_URL_1 = "https://images.example.org/iiif/2/abc123/full/max/0/default.jpg"
IMAGE_BYTES = b"abcdefghijklmnopqrstuvwxyz"


def _image_callback(request: httpx.Request) -> httpx.Response:
    range_header = request.headers.get("Range")
    if not range_header:
        return httpx.Response(status_code=200, content=IMAGE_BYTES)

    match = re.match(r"bytes=(\d+)-(\d+)?", range_header)
    if not match:
        return httpx.Response(status_code=416, content=b"")

    start = int(match.group(1))
    end_raw = match.group(2)
    end = int(end_raw) if end_raw is not None else len(IMAGE_BYTES) - 1
    return httpx.Response(status_code=206, content=IMAGE_BYTES[start : end + 1])


def _register_manifest_and_image(httpx_mock: HTTPXMock, sample_manifest_v3: JSONDict) -> None:
    httpx_mock.add_response(method="GET", url=MANIFEST_URL, json=sample_manifest_v3)
    httpx_mock.add_response(
        method="HEAD",
        url=IMAGE_URL_1,
        headers={"Content-Length": str(len(IMAGE_BYTES))},
    )
    httpx_mock.add_callback(_image_callback, method="GET", url=IMAGE_URL_1)


def test_read_full(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _register_manifest_and_image(httpx_mock, sample_manifest_v3)

    with iiif_fs.open(f"{MANIFEST_PATH}/canvas-one.jpg", "rb") as handle:
        assert handle.read(5) == b"abcde"


def test_read_chunks(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _register_manifest_and_image(httpx_mock, sample_manifest_v3)

    with iiif_fs.open(f"{MANIFEST_PATH}/canvas-one.jpg", "rb") as handle:
        assert handle.read(3) == b"abc"
        assert handle.read(3) == b"def"


def test_read_range(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _register_manifest_and_image(httpx_mock, sample_manifest_v3)

    with iiif_fs.open(f"{MANIFEST_PATH}/canvas-one.jpg", "rb") as handle:
        handle.seek(2)
        assert handle.read(4) == b"cdef"


def test_seek_and_tell(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _register_manifest_and_image(httpx_mock, sample_manifest_v3)

    with iiif_fs.open(f"{MANIFEST_PATH}/canvas-one.jpg", "rb") as handle:
        handle.seek(10)
        assert handle.tell() == 10


def test_write_raises(iiif_fs: IIIFFileSystem) -> None:
    with pytest.raises(NotImplementedError):
        iiif_fs.open(f"{MANIFEST_PATH}/canvas-one.jpg", "wb")


def test_context_manager(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _register_manifest_and_image(httpx_mock, sample_manifest_v3)

    with iiif_fs.open(f"{MANIFEST_PATH}/canvas-one.jpg", "rb") as handle:
        assert handle.read(2) == b"ab"

    assert handle.closed
