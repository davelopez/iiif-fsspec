"""Custom exceptions for the IIIF fsspec plugin."""


class IIIFError(Exception):
    """Base exception for all IIIF-related errors."""


class ManifestParseError(IIIFError):
    """Raised when a manifest cannot be parsed."""


class UnsupportedVersionError(IIIFError):
    """Raised when an unsupported IIIF version is encountered."""


class ImageFetchError(IIIFError):
    """Raised when an image cannot be fetched from the server."""


class InvalidPathError(IIIFError):
    """Raised when a path cannot be resolved to a IIIF resource."""
