"""
BODtoJSON: A zero-dependency OAGIS BOD to Flattened JSON/NDJSON converter.
"""

__version__ = "2.0.0"

from .mapper import to_json, to_ndjson, convert, BODConverter

__all__ = ["to_json", "to_ndjson", "convert", "BODConverter"]