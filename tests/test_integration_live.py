"""Live integration tests against a real IIIF manifest.

These tests require network access and are opt-in via ``pytest -m integration``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from iiif_fsspec.filesystem import IIIFFileSystem
from iiif_fsspec.path import make_resource_path

pytestmark = pytest.mark.integration

MANIFEST_URL = "https://iiif.io/api/cookbook/recipe/0001-mvm-image/manifest.json"
MANIFEST_PATH = make_resource_path(MANIFEST_URL, kind="manifest")
OUTPUT_MANIFEST_PATH = MANIFEST_PATH.removeprefix("iiif://")
BODLEIAN_COLLECTION_PATH = "https://iiif.bodleian.ox.ac.uk/iiif/collection/top"
BODLEIAN_MANIFEST_PATH = (
    "https://iiif.bodleian.ox.ac.uk/iiif/manifest/b73ca01f-aac8-4916-a7c6-3c8e67939a66.json"
)
BODLEIAN_V3_ACCEPT = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
BODLEIAN_UA = "iiif-fsspec-integration/0.1 (dev@example.org)"


@pytest.fixture(scope="module")
def live_fs() -> IIIFFileSystem:
    fs = IIIFFileSystem(timeout=30.0, skip_instance_cache=True)
    try:
        entries = fs.ls(MANIFEST_PATH, detail=True)
    except Exception as exc:  # pragma: no cover - network-dependent path
        pytest.skip(f"Live IIIF manifest is currently unavailable: {exc}")

    if not entries:
        pytest.skip("Live manifest returned no canvases")

    return fs


@pytest.fixture(scope="module")
def live_entries(live_fs: IIIFFileSystem) -> list[dict[str, object]]:
    entries = live_fs.ls(MANIFEST_PATH, detail=True)
    assert isinstance(entries, list)
    assert len(entries) > 0
    return entries


@pytest.fixture(scope="module")
def first_canvas_path(live_entries: list[dict[str, object]]) -> str:
    first_name = live_entries[0]["name"]
    assert isinstance(first_name, str)
    return first_name


def test_ls_info_exists_and_types(
    live_fs: IIIFFileSystem,
    live_entries: list[dict[str, object]],
    first_canvas_path: str,
) -> None:
    names = live_fs.ls(MANIFEST_PATH, detail=False)
    assert isinstance(names, list)
    assert len(names) == len(live_entries)
    assert first_canvas_path in names

    manifest_info = live_fs.info(MANIFEST_PATH)
    assert manifest_info["type"] == "directory"

    canvas_info = live_fs.info(first_canvas_path)
    assert canvas_info["type"] == "file"
    assert canvas_info["name"] == first_canvas_path

    assert live_fs.exists(MANIFEST_PATH)
    assert live_fs.exists(first_canvas_path)
    assert live_fs.isdir(MANIFEST_PATH)
    assert not live_fs.isfile(MANIFEST_PATH)
    assert live_fs.isfile(first_canvas_path)


def test_cat_open_head_tail_and_ranges(
    live_fs: IIIFFileSystem,
    first_canvas_path: str,
) -> None:
    chunk = live_fs.cat_file(first_canvas_path, start=0, end=256)
    assert isinstance(chunk, bytes)
    assert len(chunk) > 0

    with live_fs.open(first_canvas_path, "rb") as handle:
        payload = handle.read(256)
    assert isinstance(payload, bytes)
    assert len(payload) > 0

    head = live_fs.head(first_canvas_path, size=64)
    tail = live_fs.tail(first_canvas_path, size=64)
    assert isinstance(head, bytes)
    assert isinstance(tail, bytes)
    assert len(head) > 0
    assert len(tail) > 0

    cat_out = live_fs.cat(first_canvas_path)
    assert isinstance(cat_out, bytes)
    assert len(cat_out) > 0

    range_out = live_fs.cat_ranges([first_canvas_path], [0], [32])
    assert isinstance(range_out, list)
    assert len(range_out) == 1
    assert isinstance(range_out[0], bytes)
    assert len(range_out[0]) > 0


def test_get_file_and_get(live_fs: IIIFFileSystem, first_canvas_path: str, tmp_path: Path) -> None:
    out_one = tmp_path / "canvas-get-file.bin"
    live_fs.get_file(first_canvas_path, str(out_one))
    assert out_one.exists()
    assert out_one.stat().st_size > 0

    out_dir = tmp_path / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    live_fs.get(first_canvas_path, str(out_dir))

    downloaded = list(out_dir.rglob("*"))
    files = [path for path in downloaded if path.is_file()]
    assert len(files) >= 1
    assert any(path.stat().st_size > 0 for path in files)


def test_find_walk_glob_expand_and_du(
    live_fs: IIIFFileSystem,
    live_entries: list[dict[str, object]],
    first_canvas_path: str,
) -> None:
    found = live_fs.find(MANIFEST_PATH)
    assert isinstance(found, list)
    assert len(found) >= len(live_entries)

    walked = list(live_fs.walk(MANIFEST_PATH))
    assert len(walked) >= 1
    root, dirs, files = walked[0]
    assert str(root) == OUTPUT_MANIFEST_PATH
    assert isinstance(dirs, list)
    assert isinstance(files, list)

    globbed = live_fs.glob(f"{MANIFEST_PATH}/*")
    assert isinstance(globbed, list)
    assert len(globbed) >= 1
    assert first_canvas_path in globbed

    expanded = live_fs.expand_path(first_canvas_path)
    assert isinstance(expanded, list)
    assert len(expanded) == 1
    assert str(expanded[0]) == first_canvas_path

    total_size = live_fs.du(MANIFEST_PATH, total=True)
    assert isinstance(total_size, int)
    assert total_size >= 0

    canvas_size = live_fs.size(first_canvas_path)
    assert canvas_size is None or isinstance(canvas_size, int)


def test_bodleian_collection_hierarchical_listing() -> None:
    fs = IIIFFileSystem(timeout=30.0, skip_instance_cache=True, user_agent=BODLEIAN_UA)
    try:
        top_entries = fs.ls(BODLEIAN_COLLECTION_PATH, detail=True)
    except Exception as exc:  # pragma: no cover - network-dependent path
        pytest.skip(f"Bodleian collection endpoint unavailable: {exc}")

    if not top_entries:
        pytest.skip("Bodleian top collection returned no entries")

    first_child = str(top_entries[0]["name"])
    child_entries = fs.ls(first_child, detail=True)
    assert isinstance(child_entries, list)
    assert len(child_entries) > 0


def test_bodleian_manifest_content_negotiation_v2_and_v3() -> None:
    fs_v2 = IIIFFileSystem(timeout=30.0, skip_instance_cache=True, user_agent=BODLEIAN_UA)
    try:
        fs_v2.ls(BODLEIAN_MANIFEST_PATH, detail=True)
    except Exception as exc:  # pragma: no cover - network-dependent path
        pytest.skip(f"Bodleian manifest endpoint unavailable: {exc}")

    manifest_v2 = fs_v2._manifest_cache.get(BODLEIAN_MANIFEST_PATH)
    if manifest_v2 is None:
        pytest.skip("Bodleian v2 manifest did not populate manifest cache")
    assert manifest_v2.version == 2

    fs_v3 = IIIFFileSystem(
        timeout=30.0,
        skip_instance_cache=True,
        user_agent=BODLEIAN_UA,
        headers={"Accept": BODLEIAN_V3_ACCEPT},
    )
    try:
        fs_v3.ls(BODLEIAN_MANIFEST_PATH, detail=True)
    except Exception as exc:  # pragma: no cover - network-dependent path
        pytest.skip(f"Bodleian v3-negotiated manifest unavailable: {exc}")

    manifest_v3 = fs_v3._manifest_cache.get(BODLEIAN_MANIFEST_PATH)
    if manifest_v3 is None:
        pytest.skip("Bodleian v3 manifest did not populate manifest cache")
    assert manifest_v3.version == 3
