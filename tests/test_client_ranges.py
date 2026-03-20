"""Branch tests for client range-header handling."""

from iiif_fsspec.client import _build_range_header


def test_build_range_header_none() -> None:
    assert _build_range_header(None, None) is None


def test_build_range_header_only_end() -> None:
    assert _build_range_header(None, 10) == "bytes=0-9"
    assert _build_range_header(None, 0) is None


def test_build_range_header_only_start() -> None:
    assert _build_range_header(3, None) == "bytes=3-"


def test_build_range_header_end_before_start() -> None:
    assert _build_range_header(10, 5) == "bytes=10-"


def test_build_range_header_normal() -> None:
    assert _build_range_header(4, 9) == "bytes=4-8"
