"""Additional branch tests for filesystem helper paths."""

from __future__ import annotations

from typing import Any

import pytest

from iiif_fsspec.exceptions import InvalidPathError
from iiif_fsspec.filesystem import IIIFFileSystem
from iiif_fsspec.manifest import parse_manifest

MANIFEST_PATH = "iiif://example.org/iiif/manifest.json"
MANIFEST_URL = "https://example.org/iiif/manifest.json"
JSONDict = dict[str, Any]


def _prime_manifest_cache(iiif_fs: IIIFFileSystem, sample_manifest_v3: JSONDict) -> None:
    iiif_fs._manifest_cache[MANIFEST_URL] = parse_manifest(sample_manifest_v3)


def test_ls_on_canvas_path_returns_name_only(
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _prime_manifest_cache(iiif_fs, sample_manifest_v3)
    names = iiif_fs.ls(f"{MANIFEST_PATH}/canvas-one.jpg", detail=False)
    assert names == [f"{MANIFEST_PATH}/canvas-one.jpg"]


def test_info_missing_canvas_raises(
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _prime_manifest_cache(iiif_fs, sample_manifest_v3)
    with pytest.raises(InvalidPathError):
        iiif_fs.info(f"{MANIFEST_PATH}/does-not-exist.jpg")


def test_cat_file_manifest_path_raises(iiif_fs: IIIFFileSystem) -> None:
    with pytest.raises(InvalidPathError):
        iiif_fs.cat_file(MANIFEST_PATH)


def test_cat_file_missing_canvas_raises(
    iiif_fs: IIIFFileSystem,
    sample_manifest_v3: JSONDict,
) -> None:
    _prime_manifest_cache(iiif_fs, sample_manifest_v3)
    with pytest.raises(InvalidPathError):
        iiif_fs.cat_file(f"{MANIFEST_PATH}/missing.jpg")


def test_ls_with_malformed_stateless_member_path_raises(iiif_fs: IIIFFileSystem) -> None:
    bad_path = "iiif://example.org/iiif/collection/top/manifest-books--bad$$.json"
    with pytest.raises(InvalidPathError):
        iiif_fs.ls(bad_path)
