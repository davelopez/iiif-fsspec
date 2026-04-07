# iiif-fsspec

iiif-fsspec is a read-only [fsspec](https://filesystem-spec.readthedocs.io/) plugin for
[IIIF](https://iiif.io/) resources.

It lets you treat IIIF manifests like directories and canvas images like files, so you can use
familiar filesystem operations such as `ls`, `open`, and `cat_file`.

## What You Can Do

- List canvases in a IIIF manifest
- Read full images or byte ranges
- Browse IIIF collections
- Use either raw manifest URLs as input or tokenized paths returned by the filesystem

Supported versions:

- IIIF Presentation API v2
- IIIF Presentation API v3

## Installation

```bash
pip install iiif-fsspec
```

Or with uv:

```bash
uv add iiif-fsspec
```

## Quick Start

```python
import fsspec

fs = fsspec.filesystem("iiif")

manifest_url = "https://example.org/iiif/manifest.json"
entries = fs.ls(manifest_url, detail=True)

print(entries[0]["name"])
# manifest--<token>.json/canvas-one.jpg
print(entries[0]["iiif_label"])
# "Canvas 1"

with fs.open(entries[0]["name"], "rb") as handle:
    first_kb = handle.read(1024)

print(len(first_kb))
```

## Common Usage

List canvas paths:

```python
from iiif_fsspec import IIIFFileSystem

fs = IIIFFileSystem()
paths = fs.ls("https://example.org/iiif/manifest.json")
print(paths)
```

Read a byte range:

```python
# Assuming paths[0] is a canvas image path
chunk = fs.cat_file(paths[0], start=0, end=1024)
print(len(chunk))
```

## Examples

Runnable scripts are in [examples](examples/):

```bash
uv run python examples/browse_manifest.py
uv run python examples/browse_download_cli.py
uv run python examples/read_first_canvas.py
uv run python examples/download_canvas.py --index 1 --output /tmp/canvas-1.jpg
```

Use a different manifest:

```bash
uv run python examples/browse_manifest.py --manifest-url https://example.org/iiif/manifest.json
```

## Path Format

Returned paths are protocol-free tokenized names that are safe to reuse with `open` and `ls`:

- Manifest path: `manifest--<token>.json`
- Canvas path: `manifest--<token>.json/canvas-one.jpg`
- Collection child: `collection--<token>.json/manifest-book-1--<token>.json`

Raw `https://` and `http://` manifest URLs are accepted as entry inputs.

## Security Notes

iiif-fsspec fetches remote manifests and image resources. Treat manifest content as untrusted
network input.

- Only `http` and `https` resource URLs are accepted
- `http -> https` redirects are allowed
- `https -> http` redirects are rejected
- Non-HTTP(S) redirect targets are rejected

If you run in a sensitive environment, add your own outbound network controls (for example,
allowlists or egress filtering).

## Development

```bash
uv sync --dev
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/ tests/
uv run pytest
```

Live integration tests are opt-in:

```bash
uv run pytest -m integration -v
```

## License

MIT. See [LICENSE](LICENSE).
