"""Tests for IIIF filesystem integration behavior."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from iiif_fsspec.exceptions import InvalidPathError
from iiif_fsspec.filesystem import IIIFFileSystem
from iiif_fsspec.iiif_file import IIIFFile
from iiif_fsspec.manifest import parse_manifest

from .conftest import JSONDict

MANIFEST_PATH = "iiif://example.org/iiif/manifest.json"
MANIFEST_URL = "https://example.org/iiif/manifest.json"
IMAGE_URL_1 = "https://images.example.org/iiif/2/abc123/full/max/0/default.jpg"
V3_ACCEPT = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"


def _mock_image_size(httpx_mock: HTTPXMock, size: int = 6) -> None:
    httpx_mock.add_response(
        method="HEAD",
        url=IMAGE_URL_1,
        headers={"Content-Length": str(size)},
    )


def _prime_manifest_cache(iiif_fs: IIIFFileSystem, sample_manifest_v3: JSONDict) -> None:
    iiif_fs._manifest_cache[MANIFEST_URL] = parse_manifest(sample_manifest_v3)


def test_ls_manifest(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    httpx_mock.add_response(method="GET", url=MANIFEST_URL, json=sample_manifest_v3)

    entries = iiif_fs.ls(MANIFEST_PATH, detail=True)

    assert len(entries) == 2
    assert entries[0]["name"].endswith("/canvas-one.jpg")
    assert entries[0]["type"] == "file"


def test_info_manifest(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    del httpx_mock, sample_manifest_v3

    info = iiif_fs.info(MANIFEST_PATH)

    assert info["type"] == "directory"
    assert info["name"] == MANIFEST_PATH


def test_info_canvas(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _mock_image_size(httpx_mock)
    _prime_manifest_cache(iiif_fs, sample_manifest_v3)

    canvas_path = f"{MANIFEST_PATH}/canvas-one.jpg"
    info = iiif_fs.info(canvas_path)

    assert info["type"] == "file"
    assert info["iiif_label"] == "Canvas One"


def test_cat_file_full(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _prime_manifest_cache(iiif_fs, sample_manifest_v3)
    httpx_mock.add_response(method="GET", url=IMAGE_URL_1, content=b"abcdef")

    payload = iiif_fs.cat_file(f"{MANIFEST_PATH}/canvas-one.jpg")

    assert payload == b"abcdef"


def test_cat_file_range(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
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
    sample_manifest_v3: JSONDict,
) -> None:
    _mock_image_size(httpx_mock, size=3)
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
    sample_manifest_v3: JSONDict,
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


def test_ls_manifest_uses_accept_header(
    httpx_mock: HTTPXMock,
    sample_manifest_v3: JSONDict,
) -> None:
    fs = IIIFFileSystem(
        skip_instance_cache=True,
        headers={"Accept": V3_ACCEPT},
    )
    httpx_mock.add_response(
        method="GET",
        url=MANIFEST_URL,
        json=sample_manifest_v3,
        match_headers={"Accept": V3_ACCEPT},
    )

    names = fs.ls(MANIFEST_PATH, detail=False)

    assert len(names) == 2


def test_ls_manifest_uses_user_agent(
    httpx_mock: HTTPXMock,
    sample_manifest_v3: JSONDict,
) -> None:
    user_agent = "iiif-fsspec-tests/1.0 (dev@example.org)"
    fs = IIIFFileSystem(skip_instance_cache=True, user_agent=user_agent)
    httpx_mock.add_response(
        method="GET",
        url=MANIFEST_URL,
        json=sample_manifest_v3,
        match_headers={"User-Agent": user_agent},
    )

    names = fs.ls(MANIFEST_PATH, detail=False)

    assert len(names) == 2


def test_ls_collection_returns_directory_entries(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_collection_v2: JSONDict,
) -> None:
    collection_url = "https://example.org/iiif/collection/top"
    collection_path = "iiif://example.org/iiif/collection/top"
    httpx_mock.add_response(method="GET", url=collection_url, json=sample_collection_v2)

    entries = iiif_fs.ls(collection_path, detail=True)

    assert len(entries) == 2
    assert all(entry["type"] == "directory" for entry in entries)
    assert entries[0]["name"].startswith(f"{collection_path}/")
    assert entries[0]["name"].endswith(".json")
    assert [entry["iiif_label"] for entry in entries] == ["Books", "Book 1"]
    assert [entry["iiif_id"] for entry in entries] == [
        "https://example.org/iiif/collection/books",
        "https://example.org/iiif/manifest/book-1.json",
    ]


def test_collection_listing_uses_resource_cache(
    httpx_mock: HTTPXMock,
    sample_collection_v2: JSONDict,
) -> None:
    collection_url = "https://example.org/iiif/collection/top"
    collection_path = "iiif://example.org/iiif/collection/top"
    fs = IIIFFileSystem(skip_instance_cache=True)
    httpx_mock.add_response(method="GET", url=collection_url, json=sample_collection_v2)

    fs.ls(collection_path)
    fs.ls(collection_path)

    collection_requests = [
        req for req in httpx_mock.get_requests() if str(req.url) == collection_url
    ]
    assert len(collection_requests) == 1


def test_ls_child_manifest_from_collection_member_path(
    httpx_mock: HTTPXMock,
    iiif_fs: IIIFFileSystem,
    sample_collection_v2: JSONDict,
    sample_manifest_v3: JSONDict,
) -> None:
    collection_url = "https://example.org/iiif/collection/top"
    collection_path = "iiif://example.org/iiif/collection/top"
    child_manifest_url = "https://example.org/iiif/manifest/book-1.json"
    httpx_mock.add_response(method="GET", url=collection_url, json=sample_collection_v2)
    httpx_mock.add_response(method="GET", url=child_manifest_url, json=sample_manifest_v3)

    collection_entries = iiif_fs.ls(collection_path, detail=True)
    manifest_entries = [
        entry for entry in collection_entries if entry["iiif_resource_type"] == "manifest"
    ]

    assert len(manifest_entries) == 1
    child_manifest_path = str(manifest_entries[0]["name"])
    assert manifest_entries[0]["iiif_label"] == "Book 1"
    assert manifest_entries[0]["iiif_id"] == child_manifest_url
    child_entries = iiif_fs.ls(child_manifest_path, detail=True)

    assert len(child_entries) == 2
    assert all(entry["type"] == "file" for entry in child_entries)


def test_collection_child_path_is_stateless_across_fresh_instances(
    httpx_mock: HTTPXMock,
    sample_collection_v2: JSONDict,
    sample_manifest_v3: JSONDict,
) -> None:
    collection_url = "https://example.org/iiif/collection/top"
    collection_path = "iiif://example.org/iiif/collection/top"
    child_manifest_url = "https://example.org/iiif/manifest/book-1.json"

    fs_a = IIIFFileSystem(skip_instance_cache=True)
    fs_b = IIIFFileSystem(skip_instance_cache=True)

    httpx_mock.add_response(method="GET", url=collection_url, json=sample_collection_v2)
    httpx_mock.add_response(method="GET", url=child_manifest_url, json=sample_manifest_v3)

    collection_entries = fs_a.ls(collection_path, detail=True)
    child_manifest_paths = [
        str(entry["name"])
        for entry in collection_entries
        if entry["iiif_resource_type"] == "manifest"
    ]

    assert len(child_manifest_paths) == 1

    child_entries = fs_b.ls(child_manifest_paths[0], detail=True)

    assert len(child_entries) == 2
    assert all(entry["type"] == "file" for entry in child_entries)


def test_nested_collection_paths_are_stateless_across_fresh_instances(
    httpx_mock: HTTPXMock,
    sample_manifest_v3: JSONDict,
) -> None:
    top_collection_url = "https://example.org/iiif/collection/top"
    top_collection_path = "iiif://example.org/iiif/collection/top"
    nested_collection_url = "https://example.org/iiif/collection/books"
    child_manifest_url = "https://example.org/iiif/manifest/book-1.json"

    top_collection_payload = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": top_collection_url,
        "@type": "sc:Collection",
        "label": "Top Collection",
        "collections": [
            {
                "@id": nested_collection_url,
                "@type": "sc:Collection",
                "label": "Books",
            }
        ],
    }
    nested_collection_payload = {
        "@context": "http://iiif.io/api/presentation/2/context.json",
        "@id": nested_collection_url,
        "@type": "sc:Collection",
        "label": "Books",
        "manifests": [
            {
                "@id": child_manifest_url,
                "@type": "sc:Manifest",
                "label": "Book 1",
            }
        ],
    }

    fs_a = IIIFFileSystem(skip_instance_cache=True)
    fs_b = IIIFFileSystem(skip_instance_cache=True)
    fs_c = IIIFFileSystem(skip_instance_cache=True)

    httpx_mock.add_response(method="GET", url=top_collection_url, json=top_collection_payload)
    httpx_mock.add_response(method="GET", url=nested_collection_url, json=nested_collection_payload)
    httpx_mock.add_response(method="GET", url=child_manifest_url, json=sample_manifest_v3)

    top_entries = fs_a.ls(top_collection_path, detail=True)
    nested_paths = [
        str(entry["name"]) for entry in top_entries if entry["iiif_resource_type"] == "collection"
    ]
    assert len(nested_paths) == 1

    nested_entries = fs_b.ls(nested_paths[0], detail=True)
    manifest_paths = [
        str(entry["name"]) for entry in nested_entries if entry["iiif_resource_type"] == "manifest"
    ]
    assert len(manifest_paths) == 1

    canvas_entries = fs_c.ls(manifest_paths[0], detail=True)
    assert len(canvas_entries) == 2
    assert all(entry["type"] == "file" for entry in canvas_entries)
