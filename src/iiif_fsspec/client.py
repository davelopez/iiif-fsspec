"""Async HTTP client wrapper for IIIF resources."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

import httpx

from iiif_fsspec.exceptions import ImageFetchError, ManifestParseError

_MAX_REDIRECTS = 10


class AsyncIIIFClient:
    """Async HTTP client for IIIF resources using ``httpx``."""

    def __init__(
        self,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            timeout: Timeout in seconds for requests.
            headers: Optional headers applied to all requests.
        """
        self._timeout = timeout
        self._headers = headers or {}
        self._client: httpx.AsyncClient | None = None
        self._size_cache: dict[str, int] = {}

    async def get_json(self, url: str) -> dict[str, Any]:
        """Fetch and parse JSON content from a URL.

        Args:
            url: Resource URL.

        Returns:
            Parsed JSON dictionary.

        Raises:
            ImageFetchError: If the request fails or returns HTTP error.
            ManifestParseError: If the response is not a JSON object.
        """
        response = await self._request("GET", url)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ManifestParseError(f"Invalid JSON payload from {url}") from exc

        if not isinstance(payload, dict):
            raise ManifestParseError(f"Expected JSON object from {url}")
        return payload

    async def get_bytes(
        self,
        url: str,
        start: int | None = None,
        end: int | None = None,
    ) -> bytes:
        """Fetch bytes with optional range requests.

        The ``end`` offset is treated as exclusive to match fsspec slicing.

        Args:
            url: Resource URL.
            start: Optional start offset.
            end: Optional exclusive end offset.

        Returns:
            Response body bytes.

        Raises:
            ImageFetchError: If the request fails.
        """
        headers: dict[str, str] = {}
        range_header = _build_range_header(start, end)
        if range_header is not None:
            headers["Range"] = range_header

        response = await self._request("GET", url, headers=headers)
        return response.content

    async def get_image_info(self, service_url: str) -> dict[str, Any]:
        """Fetch IIIF image ``info.json`` for a service endpoint."""
        info_url = f"{service_url.rstrip('/')}/info.json"
        return await self.get_json(info_url)

    async def get_size(self, url: str) -> int | None:
        """Resolve remote content length in bytes, when exposed by the server."""
        cached = self._size_cache.get(url)
        if cached is not None:
            return cached

        try:
            head_response = await self._request("HEAD", url)
            size = _parse_content_length(head_response)
            if size is not None:
                self._size_cache[url] = size
                return size
        except ImageFetchError:
            pass

        try:
            probe_response = await self._request("GET", url, headers={"Range": "bytes=0-0"})
            size = _parse_content_range_total(probe_response)
            if size is not None:
                self._size_cache[url] = size
                return size
        except ImageFetchError:
            pass

        return None

    async def close(self) -> None:
        """Close the underlying httpx client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Issue an HTTP request and normalize errors."""
        client = self._get_client()
        try:
            _validate_url_scheme(url)
            request = client.build_request(method, url, headers=headers)

            for _ in range(_MAX_REDIRECTS + 1):
                response = await client.send(request, follow_redirects=False)
                if not response.has_redirect_location:
                    response.raise_for_status()
                    return response

                next_request = response.next_request
                if next_request is None:
                    response.raise_for_status()
                    return response

                _validate_redirect_target(str(request.url), str(next_request.url))
                await response.aread()
                request = next_request

            raise ImageFetchError(f"Too many redirects while fetching IIIF resource: {url}")
        except httpx.HTTPError as exc:
            raise ImageFetchError(f"Failed to fetch IIIF resource: {url}") from exc

    def _get_client(self) -> httpx.AsyncClient:
        """Lazily create and return the shared ``httpx.AsyncClient``."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers=self._headers,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client


def _validate_url_scheme(url: str) -> None:
    """Reject unsupported URL schemes before making outbound requests."""
    scheme = urlsplit(url).scheme.lower()
    if scheme not in {"http", "https"}:
        raise ImageFetchError(f"Unsupported URL scheme for IIIF resource: {url}")


def _validate_redirect_target(source_url: str, target_url: str) -> None:
    """Allow safe redirects while rejecting insecure transport downgrades."""
    _validate_url_scheme(target_url)

    source = urlsplit(source_url)
    target = urlsplit(target_url)
    if source.scheme.lower() == "https" and target.scheme.lower() != "https":
        raise ImageFetchError(
            f"Refusing insecure redirect for IIIF resource: {source_url} -> {target_url}"
        )


def _build_range_header(start: int | None, end: int | None) -> str | None:
    """Build an HTTP Range header for byte requests.

    Args:
        start: Inclusive start byte offset.
        end: Exclusive end byte offset.

    Returns:
        A valid Range header value, or ``None`` for full-content requests.
    """
    if start is None and end is None:
        return None

    if start is None:
        if end is None or end <= 0:
            return None
        return f"bytes=0-{end - 1}"

    if end is None:
        return f"bytes={start}-"

    if end <= start:
        return f"bytes={start}-"

    return f"bytes={start}-{end - 1}"


def _parse_content_length(response: httpx.Response) -> int | None:
    """Parse Content-Length from response headers."""
    header = response.headers.get("Content-Length")
    if header is None:
        return None
    try:
        value = int(header)
    except ValueError:
        return None
    return value if value >= 0 else None


def _parse_content_range_total(response: httpx.Response) -> int | None:
    """Parse total object size from a Content-Range header."""
    header = response.headers.get("Content-Range")
    if header is None:
        return None
    match = re.match(r"bytes\s+\d+-\d+/(\d+)", header)
    if match is None:
        return None
    try:
        value = int(match.group(1))
    except ValueError:
        return None
    return value if value >= 0 else None
