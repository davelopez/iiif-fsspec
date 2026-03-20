"""Shared test fixtures for iiif-fsspec tests."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from iiif_fsspec.client import AsyncIIIFClient
from iiif_fsspec.filesystem import IIIFFileSystem


@pytest.fixture
def sample_manifest_v3() -> dict:
    """Sample IIIF Presentation API v3 manifest."""
    fixture_path = Path(__file__).parent / "data" / "manifest_v3.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def sample_manifest_v2() -> dict:
    """Sample IIIF Presentation API v2 manifest."""
    fixture_path = Path(__file__).parent / "data" / "manifest_v2.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
async def mock_iiif_client(httpx_mock: HTTPXMock) -> AsyncGenerator[AsyncIIIFClient, None]:
    """Mock IIIF client backed by pytest-httpx."""
    del httpx_mock
    client = AsyncIIIFClient()
    yield client
    await client.close()


@pytest.fixture
def iiif_fs() -> IIIFFileSystem:
    """Pre-configured IIIF filesystem for testing."""
    return IIIFFileSystem(skip_instance_cache=True)
