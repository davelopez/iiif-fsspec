"""Live integration tests against a real IIIF manifest.

These tests require network access and are opt-in via ``pytest -m integration``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from iiif_fsspec.filesystem import IIIFFileSystem

pytestmark = pytest.mark.integration

MANIFEST_URL = "https://iiif.io/api/cookbook/recipe/0001-mvm-image/manifest.json"
MANIFEST_PATH = "iiif://iiif.io/api/cookbook/recipe/0001-mvm-image/manifest.json"


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
    assert str(root).endswith("iiif.io/api/cookbook/recipe/0001-mvm-image/manifest.json")
    assert isinstance(dirs, list)
    assert isinstance(files, list)

    globbed = live_fs.glob(f"{MANIFEST_PATH}/*")
    assert isinstance(globbed, list)
    assert len(globbed) >= 1
    assert first_canvas_path in globbed

    expanded = live_fs.expand_path(first_canvas_path)
    assert isinstance(expanded, list)
    assert len(expanded) == 1
    assert str(expanded[0]).endswith(
        "iiif.io/api/cookbook/recipe/0001-mvm-image/manifest.json/p1.png"
    )

    total_size = live_fs.du(MANIFEST_PATH, total=True)
    assert isinstance(total_size, int)
    assert total_size >= 0

    canvas_size = live_fs.size(first_canvas_path)
    assert canvas_size is None or isinstance(canvas_size, int)
