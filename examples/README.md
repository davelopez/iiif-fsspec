# Real-world examples

These scripts use a real IIIF manifest:

- https://api.irht.cnrs.fr/ark:/63955/fbkub82u5bw7/manifest.json

Run from repository root:

```bash
uv run python examples/browse_manifest.py
uv run python examples/read_first_canvas.py
uv run python examples/download_canvas.py --index 1 --output /tmp/canvas-1.jpg
```

Use a different source manifest:

```bash
uv run python examples/browse_manifest.py --manifest-url https://example.org/iiif/manifest.json
```
