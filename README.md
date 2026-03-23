# iiif-fsspec

`iiif-fsspec` is a read-only [`fsspec`](https://filesystem-spec.readthedocs.io/) plugin for
[IIIF](https://iiif.io/) (International Image Interoperability Framework) resources.

It exposes a IIIF manifest as a directory and canvas images as files.

Two path styles are accepted interchangeably:

| Style | Example |
|-------|---------|
| `iiif://` (registered fsspec protocol) | `iiif://example.org/iiif/manifest.json` |
| `https://` / `http://` (raw manifest URL) | `https://example.org/iiif/manifest.json` |

Returned paths always preserve the style of the caller's input:

- `iiif://example.org/iiif/manifest.json` → directory
- `iiif://example.org/iiif/manifest.json/canvas-one.jpg` → file
- `https://example.org/iiif/manifest.json` → directory
- `https://example.org/iiif/manifest.json/canvas-one.jpg` → file

The plugin supports both IIIF Presentation API v2 and v3 manifests with automatic version
detection.

## Overview

This package lets data-access systems use IIIF manifests through the standard fsspec filesystem
interface. That means you can call `ls`, `info`, `open`, and `cat_file` on IIIF URLs and treat
them like regular filesystem paths.

Current scope:

- Read-only operations
- Manifest listing to canvas file entries
- Full image reads and range reads
- In-memory manifest caching

## Installation

Using `uv`:

```bash
uv add iiif-fsspec
```

Using `pip`:

```bash
pip install iiif-fsspec
```

## Quick Start

```python
import fsspec

fs = fsspec.filesystem("iiif")

# Both https:// and iiif:// paths are accepted; returned names mirror the input style.

# List canvases using a raw manifest URL
entries = fs.ls("https://example.org/iiif/manifest.json", detail=True)

# Read a canvas image
with fs.open("https://example.org/iiif/manifest.json/canvas-one.jpg", "rb") as handle:
	image_bytes = handle.read()
```

## Usage Examples

### Python API

```python
from iiif_fsspec import IIIFFileSystem

fs = IIIFFileSystem()

# Using a raw https:// manifest URL
paths = fs.ls("https://example.org/iiif/manifest.json")
print(paths)  # ['https://example.org/iiif/manifest.json/canvas-one.jpg', ...]

chunk = fs.cat_file("https://example.org/iiif/manifest.json/canvas-one.jpg", start=0, end=1024)
print(len(chunk))
```

### fsspec.open Integration

```python
import fsspec

# Use the iiif:// scheme with fsspec.open (routes to IIIFFileSystem via entry-point)
with fsspec.open("iiif://example.org/iiif/manifest.json/canvas-one.jpg", "rb") as handle:
	first_kb = handle.read(1024)

# Or instantiate IIIFFileSystem directly with a plain https:// URL
from iiif_fsspec import IIIFFileSystem

fs = IIIFFileSystem()
with fs.open("https://example.org/iiif/manifest.json/canvas-one.jpg", "rb") as handle:
	first_kb = handle.read(1024)
```

## Real-World Examples

The [examples](examples/) folder includes runnable scripts that browse a real IIIF manifest:

- `https://api.irht.cnrs.fr/ark:/63955/fbkub82u5bw7/manifest.json`

From the repository root:

```bash
uv run python examples/browse_manifest.py
uv run python examples/read_first_canvas.py
uv run python examples/download_canvas.py --index 1 --output /tmp/canvas-1.jpg
```

To target a different manifest:

```bash
uv run python examples/browse_manifest.py --manifest-url https://example.org/iiif/manifest.json
```

## Supported IIIF Versions

- IIIF Presentation API v2
- IIIF Presentation API v3

Version detection uses manifest metadata (`@context`, `type`, and `@type`) and dispatches to the
appropriate parser.

## Security Notes

`iiif-fsspec` fetches manifests, image resources, and `info.json` endpoints from remote servers.
Treat manifest content as a source of outbound network locations, not just metadata.

Current network policy:

- Only `http` and `https` resource URLs are accepted.
- Redirects are followed only through an explicit policy in the HTTP client.
- `http -> https` redirects are allowed.
- `https -> http` redirects are rejected.
- Non-HTTP(S) redirect targets are rejected.

Operational implications:

- A manifest can point to image or IIIF service URLs on arbitrary hosts.
- Redirects can move a request to a different host, as long as the redirect stays within the
	allowed transport policy above.
- This package is intended for public IIIF resources and does not add host allowlisting or SSRF
	protections on top of normal URL validation.

If you process manifests from untrusted sources or run this library in a sensitive environment,
consider wrapping it with your own outbound network controls, such as host allowlists, egress
filtering, or sandboxing.

## Architecture

Main modules:

- `src/iiif_fsspec/filesystem.py`: fsspec filesystem implementation
- `src/iiif_fsspec/iiif_file.py`: read-only file object for image access
- `src/iiif_fsspec/client.py`: async HTTP client wrapper (`httpx`)
- `src/iiif_fsspec/manifest.py`: IIIF v2/v3 manifest parsing
- `src/iiif_fsspec/path.py`: fsspec path <-> IIIF URL resolution
- `src/iiif_fsspec/types.py`: dataclasses and parser protocol
- `src/iiif_fsspec/exceptions.py`: package exception hierarchy

## Development

Install dependencies:

```bash
uv sync --dev
```

Run checks:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy
uv run pytest --cov=iiif_fsspec --cov-report=term-missing

# Run live-network integration tests (opt-in, requires network access)
uv run pytest -m integration -v
```

CI test strategy:

- Default CI runs fast deterministic tests and excludes live integration tests.
- A separate `Integration` workflow runs real-network tests against:
	`https://iiif.io/api/cookbook/recipe/0001-mvm-image/manifest.json`.
- The integration workflow is triggered manually (`workflow_dispatch`) and on a low-frequency schedule.

Pre-commit hooks are configured in `.pre-commit-config.yaml`.

## License

MIT. See `LICENSE`.

## Acknowledgments

- [fsspec](https://filesystem-spec.readthedocs.io/)
- [httpx](https://www.python-httpx.org/)
- [piffle](https://github.com/Princeton-CDH/piffle)
- IIIF community and specification authors
