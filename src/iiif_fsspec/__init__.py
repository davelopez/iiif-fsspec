"""IIIF fsspec plugin.

Provides a read-only filesystem interface for IIIF resources.
"""

from iiif_fsspec.filesystem import IIIFFileSystem

__version__ = "0.1.0"
__all__ = ["IIIFFileSystem"]
