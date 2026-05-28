"""
BODtoJSON: A high-performance OAGIS BOD to Flattened JSON/NDJSON converter.
"""

__version__ = "1.1.0"

# Expose both legacy and modern functionality at the top level
from .mapper import to_json, to_ndjson, convert, BODConverter

__all__ = ["to_json", "to_ndjson", "convert", "BODConverter"]