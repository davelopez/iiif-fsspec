"""Tests for the async IIIF HTTP client."""

from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from iiif_fsspec.client import AsyncIIIFClient
from iiif_fsspec.exceptions import ImageFetchError, ManifestParseError


@pytest.mark.asyncio
async def test_get_json_success(httpx_mock: HTTPXMock) -> None:
    client = AsyncIIIFClient()
    httpx_mock.add_response(
        method="GET",
        url="https://example.org/manifest.json",
        json={"id": "https://example.org/manifest.json"},
    )

    data = await client.get_json("https://example.org/manifest.json")
    assert data["id"] == "https://example.org/manifest.json"
    await client.close()


@pytest.mark.asyncio
async def test_get_bytes_success(httpx_mock: HTTPXMock) -> None:
    client = AsyncIIIFClient()
    httpx_mock.add_response(
        method="GET",
        url="https://example.org/image.jpg",
        content=b"abcdef",
    )

    payload = await client.get_bytes("https://example.org/image.jpg")
    assert payload == b"abcdef"
    await client.close()


@pytest.mark.asyncio
async def test_get_bytes_range_header(httpx_mock: HTTPXMock) -> None:
    client = AsyncIIIFClient()
    httpx_mock.add_response(
        method="GET",
        url="https://example.org/image.jpg",
        content=b"cde",
        match_headers={"Range": "bytes=2-4"},
    )

    payload = await client.get_bytes("https://example.org/image.jpg", start=2, end=5)
    assert payload == b"cde"
    await client.close()


@pytest.mark.asyncio
async def test_http_error_raises_image_fetch_error(httpx_mock: HTTPXMock) -> None:
    client = AsyncIIIFClient()
    httpx_mock.add_response(method="GET", url="https://example.org/missing.jpg", status_code=404)

    with pytest.raises(ImageFetchError):
        await client.get_bytes("https://example.org/missing.jpg")
    await client.close()


@pytest.mark.asyncio
async def test_timeout_maps_to_image_fetch_error(httpx_mock: HTTPXMock) -> None:
    client = AsyncIIIFClient(timeout=0.1)
    httpx_mock.add_exception(
        httpx.ReadTimeout("timed out", request=httpx.Request("GET", "https://example.org/x"))
    )

    with pytest.raises(ImageFetchError):
        await client.get_bytes("https://example.org/x")
    await client.close()


@pytest.mark.asyncio
async def test_non_object_json_raises_manifest_parse_error(httpx_mock: HTTPXMock) -> None:
    client = AsyncIIIFClient()
    httpx_mock.add_response(method="GET", url="https://example.org/list.json", json=[1, 2, 3])

    with pytest.raises(ManifestParseError):
        await client.get_json("https://example.org/list.json")
    await client.close()


@pytest.mark.asyncio
async def test_get_image_info(httpx_mock: HTTPXMock) -> None:
    client = AsyncIIIFClient()
    httpx_mock.add_response(
        method="GET",
        url="https://images.example.org/iiif/2/abc/info.json",
        json={"id": "https://images.example.org/iiif/2/abc"},
    )

    data = await client.get_image_info("https://images.example.org/iiif/2/abc")
    assert data["id"] == "https://images.example.org/iiif/2/abc"
    await client.close()
