"""Interactive CLI to browse IIIF collections/manifests and download canvas images.

Usage:
    uv run python examples/browse_download_cli.py
    uv run python examples/browse_download_cli.py --manifest-url https://iiif.bodleian.ox.ac.uk/iiif/collection/top
    uv run python examples/browse_download_cli.py --accept-v3 --user-agent "iiif-fsspec-cli/1.0"
"""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path
from typing import cast

from common import DEFAULT_MANIFEST_URL, to_iiif_path

from iiif_fsspec import IIIFFileSystem
from iiif_fsspec.types import IIIFEntryInfo

V3_ACCEPT = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    LIGHT_BLUE = "\033[94m"


def paint(text: str, color: str, *, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{color}{text}{Colors.RESET}"


def human_size(num_bytes: int) -> str:
    """Format byte counts into a compact human-readable size string."""
    size = float(max(num_bytes, 0))
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactively browse IIIF resources and download images"
    )
    parser.add_argument(
        "--manifest-url",
        default=DEFAULT_MANIFEST_URL,
        help="Starting IIIF URL/path (manifest or collection; HTTP(S) or iiif://)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Rows to show per listing",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--user-agent",
        default="iiif-fsspec-cli/1.0 (dev@example.org)",
        help="User-Agent header value",
    )
    parser.add_argument(
        "--accept-v3",
        action="store_true",
        help="Send IIIF Presentation v3 Accept profile header",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show additional metadata in listings and command output",
    )
    return parser.parse_args()


def parent_path(path: str) -> str:
    stripped = path.removeprefix("iiif://")
    parts = [part for part in stripped.split("/") if part]
    if len(parts) <= 1:
        return path
    return f"iiif://{'/'.join(parts[:-1])}"


def resolve_target(token: str, entries: list[IIIFEntryInfo]) -> str:
    if token.isdigit():
        index = int(token)
        if index < 1 or index > len(entries):
            raise ValueError(f"Index out of range: {index}")
        return str(entries[index - 1]["name"])
    if token.startswith(("http://", "https://", "iiif://")):
        return to_iiif_path(token)
    return token


def print_help(colors: bool) -> None:
    print(paint("Commands:", Colors.BOLD, enabled=colors))
    print("  ls [N]                  List current directory (optional limit)")
    print("  refresh                 Re-fetch and print current listing")
    print("  find <text>             Search current folder using filesystem find")
    print("  cd <index|path|..>      Enter directory by index/path or go up")
    print("  info <index|path>       Show detailed metadata")
    print("  get <index|path> [out]  Download image file")
    print("  verbose [on|off|toggle] Show or update verbose mode")
    print("  pwd                     Show current path")
    print("  help                    Show this help")
    print("  quit                    Exit")


def print_path_line(path: str, *, colors: bool) -> None:
    print(f"      {paint(path, Colors.DIM, enabled=colors)}")


def list_entries(
    entries: list[IIIFEntryInfo],
    *,
    max_rows: int,
    colors: bool,
    verbose: bool,
) -> None:
    if not entries:
        print(paint("(empty)", Colors.DIM, enabled=colors))
        return

    displayed = entries[:max_rows]
    labels: list[str] = []
    for entry in displayed:
        label = str(entry.get("iiif_label", "")).strip()
        path = str(entry.get("name", ""))
        if not label:
            label = path.rsplit("/", maxsplit=1)[-1]
        labels.append(label)

    label_width = max(len("LABEL"), *(len(label) for label in labels))
    header = f"{'#':<4} {'KIND':<5} {'LABEL':<{label_width}} {'SIZE':>9}"
    print(paint(header, Colors.BOLD, enabled=colors))
    print(paint("-" * len(header), Colors.DIM, enabled=colors))

    for idx, entry in enumerate(displayed, start=1):
        entry_type = str(entry.get("type", "?"))
        marker = "DIR" if entry_type == "directory" else "IMG"
        marker_color = Colors.BLUE if entry_type == "directory" else Colors.GREEN
        marker_text = paint(marker, marker_color, enabled=colors)
        label = str(entry.get("iiif_label", "")).strip()
        path = str(entry.get("name", ""))
        if not label:
            label = path.rsplit("/", maxsplit=1)[-1]

        size_value = "-"
        if entry_type == "file":
            size = int(entry.get("size", 0) or 0)
            size_value = human_size(size)

        print(f"{idx:<4} {marker_text:<5} {label:<{label_width}} {size_value:>9}")
        if verbose:
            print_path_line(path, colors=colors)

    if len(entries) > max_rows:
        extra = len(entries) - max_rows
        print(paint(f"... and {extra} more", Colors.DIM, enabled=colors))


def find_entries(
    fs: IIIFFileSystem,
    current_path: str,
    query: str,
) -> list[IIIFEntryInfo]:
    """Search only the current folder using filesystem find results."""
    found = fs.find(current_path, detail=True, withdirs=True, maxdepth=1)
    detailed = cast(dict[str, dict[str, object]], found)

    lowered = query.lower()
    entries: list[IIIFEntryInfo] = []
    for item in detailed.values():
        entry = IIIFEntryInfo(item)
        name = str(entry.get("name", ""))
        if name == current_path:
            continue
        haystack = " ".join(
            [
                name,
                str(entry.get("iiif_label", "")),
                str(entry.get("iiif_resource_type", "")),
            ]
        ).lower()
        if lowered in haystack:
            entries.append(entry)

    return sorted(entries, key=lambda item: str(item.get("name", "")))


def infer_current_label(
    current_path: str,
    entries: list[IIIFEntryInfo],
    info: IIIFEntryInfo,
) -> str:
    label = str(info.get("iiif_label", "")).strip()
    if label:
        return label

    prefixes: set[str] = set()
    for entry in entries:
        child_label = str(entry.get("iiif_label", "")).strip()
        if not child_label:
            continue
        if ":" in child_label:
            prefixes.add(child_label.split(":", maxsplit=1)[0].strip())

    if len(prefixes) == 1:
        return next(iter(prefixes))

    tail = current_path.rsplit("/", maxsplit=1)[-1]
    return tail or current_path


def infer_current_identifier(current_path: str, info: IIIFEntryInfo) -> str:
    for key in ("iiif_id", "id", "uri", "name"):
        value = str(info.get(key, "")).strip()
        if value:
            return value
    return current_path


def main() -> None:
    args = parse_args()
    colors = not args.no_color
    verbose = bool(args.verbose)
    max_rows = max(int(args.limit), 1)

    headers: dict[str, str] = {}
    if args.accept_v3:
        headers["Accept"] = V3_ACCEPT

    fs: IIIFFileSystem = IIIFFileSystem(
        timeout=args.timeout,
        skip_instance_cache=True,
        user_agent=args.user_agent,
        headers=headers,
    )

    current_path = to_iiif_path(args.manifest_url)
    entries: list[IIIFEntryInfo] = []
    needs_listing = True

    print(paint("IIIF Browser CLI", Colors.BOLD, enabled=colors))
    print(paint("Type 'help' for commands.", Colors.DIM, enabled=colors))

    while True:
        if needs_listing:
            try:
                entries = cast(list[IIIFEntryInfo], fs.ls(current_path, detail=True))
            except Exception as exc:
                print(
                    paint(
                        f"error listing {current_path}: {exc}",
                        Colors.RED,
                        enabled=colors,
                    )
                )
                return

            print()
            current_id = current_path
            try:
                current_info = cast(IIIFEntryInfo, fs.info(current_path))
                current_label = infer_current_label(current_path, entries, current_info)
                current_id = infer_current_identifier(current_path, current_info)
            except Exception:
                current_label = current_path.rsplit("/", maxsplit=1)[-1] or current_path
            print(paint(f"Current: {current_label}", Colors.CYAN, enabled=colors))
            print(paint(f"      ID: {current_id}", Colors.DIM, enabled=colors))
            list_entries(
                entries,
                max_rows=max_rows,
                colors=colors,
                verbose=verbose,
            )
            needs_listing = False

        try:
            prompt_prefix = "iiif[v]" if verbose else "iiif"
            raw = input(paint(f"{prompt_prefix}> ", Colors.YELLOW, enabled=colors)).strip()
        except EOFError:
            print()
            break

        if not raw:
            continue

        try:
            parts = shlex.split(raw)
        except ValueError as exc:
            print(paint(f"invalid command syntax: {exc}", Colors.RED, enabled=colors))
            continue

        command = parts[0].lower()

        if command in {"q", "quit", "exit"}:
            break

        if command in {"h", "help", "?"}:
            print_help(colors)
            continue

        if command == "pwd":
            print(current_path)
            continue

        if command in {"refresh", "r"}:
            needs_listing = True
            continue

        if command == "verbose":
            if len(parts) == 1:
                state = "on" if verbose else "off"
                print(f"verbose: {state}")
                continue
            if len(parts) != 2:
                print(paint("usage: verbose [on|off|toggle]", Colors.RED, enabled=colors))
                continue
            action = parts[1].lower()
            if action == "on":
                verbose = True
            elif action == "off":
                verbose = False
            elif action in {"toggle", "t"}:
                verbose = not verbose
            else:
                print(paint("usage: verbose [on|off|toggle]", Colors.RED, enabled=colors))
                continue
            state = "on" if verbose else "off"
            print(f"verbose: {state}")
            needs_listing = True
            continue

        if command == "ls":
            if len(parts) > 1:
                if not parts[1].isdigit():
                    print(paint("ls expects an integer limit", Colors.RED, enabled=colors))
                    continue
                max_rows = max(int(parts[1]), 1)
            needs_listing = True
            continue

        if command == "find":
            if len(parts) < 2:
                print(paint("usage: find <text>", Colors.RED, enabled=colors))
                continue
            query = " ".join(parts[1:]).strip()
            if not query:
                print(paint("usage: find <text>", Colors.RED, enabled=colors))
                continue
            try:
                matched = find_entries(fs, current_path, query)
            except Exception as exc:
                print(paint(f"search failed: {exc}", Colors.RED, enabled=colors))
                continue
            print(
                paint(
                    f"matches for {query!r}: {len(matched)}",
                    Colors.CYAN,
                    enabled=colors,
                )
            )
            # Keep numeric index navigation aligned with the most recently displayed result set.
            entries = matched
            list_entries(
                matched,
                max_rows=max_rows,
                colors=colors,
                verbose=verbose,
            )
            continue

        if command == "cd":
            if len(parts) != 2:
                print(paint("usage: cd <index|path|..>", Colors.RED, enabled=colors))
                continue
            token = parts[1]
            if token == "..":
                current_path = parent_path(current_path)
                needs_listing = True
                continue

            try:
                target_path = resolve_target(token, entries)
                info = cast(IIIFEntryInfo, fs.info(target_path))
            except Exception as exc:
                print(paint(f"cannot resolve target: {exc}", Colors.RED, enabled=colors))
                continue

            if str(info.get("type")) != "directory":
                print(paint("target is not a directory", Colors.RED, enabled=colors))
                continue
            current_path = target_path
            needs_listing = True
            continue

        if command == "info":
            if len(parts) != 2:
                print(paint("usage: info <index|path>", Colors.RED, enabled=colors))
                continue
            try:
                target_path = resolve_target(parts[1], entries)
                info = cast(IIIFEntryInfo, fs.info(target_path))
            except Exception as exc:
                print(paint(f"cannot fetch info: {exc}", Colors.RED, enabled=colors))
                continue
            for key in sorted(info):
                print(f"{key}: {info[key]}")
            continue

        if command in {"get", "download"}:
            if len(parts) < 2 or len(parts) > 3:
                print(
                    paint(
                        "usage: get <index|path> [output-file]",
                        Colors.RED,
                        enabled=colors,
                    )
                )
                continue

            try:
                target_path = resolve_target(parts[1], entries)
                info = cast(IIIFEntryInfo, fs.info(target_path))
            except Exception as exc:
                print(paint(f"cannot resolve file target: {exc}", Colors.RED, enabled=colors))
                continue

            if str(info.get("type")) != "file":
                print(paint("target is not a file", Colors.RED, enabled=colors))
                continue

            output_path = (
                Path(parts[2])
                if len(parts) == 3
                else Path(str(target_path).rsplit("/", maxsplit=1)[-1])
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                fs.get_file(target_path, str(output_path))
            except Exception as exc:
                print(paint(f"download failed: {exc}", Colors.RED, enabled=colors))
                continue

            print(
                paint(
                    f"saved: {output_path.resolve()}",
                    Colors.GREEN,
                    enabled=colors,
                )
            )
            if verbose:
                size = int(info.get("size", 0) or 0)
                print(f"bytes: {size} ({human_size(size)})")
            continue

        print(paint("unknown command; type 'help'", Colors.RED, enabled=colors))


if __name__ == "__main__":
    main()
