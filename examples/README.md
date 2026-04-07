# Real-world examples

These scripts use a real IIIF manifest:

- https://iiif.io/api/cookbook/recipe/0001-mvm-image/manifest.json

Run from repository root:

```bash
uv run python examples/browse_manifest.py
uv run python examples/browse_download_cli.py
uv run python examples/read_first_canvas.py
uv run python examples/download_canvas.py --index 1 --output /tmp/canvas-1.jpg
```

Use a different source manifest:

```bash
uv run python examples/browse_manifest.py --manifest-url https://example.org/iiif/manifest.json
uv run python examples/browse_download_cli.py --manifest-url https://iiif.bodleian.ox.ac.uk/iiif/collection/top
```

Interactive CLI quick commands:

```text
ls [N]                  List current directory (optional limit)
find <text>             Search current folder via filesystem find
cd <index|path|..>      Enter collection/manifest directory
info <index|path>       Show metadata for entry
get <index|path> [out]  Download selected image file
pwd                     Show current path
help                    Show command help
quit                    Exit
```
