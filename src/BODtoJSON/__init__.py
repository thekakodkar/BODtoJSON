"""
BODtoJSON: A zero-dependency OAGIS BOD to Flattened JSON/NDJSON & Schema Projection engine.
"""

__version__ = "2.1.0"

from .mapper import to_json, to_ndjson, to_records, project, convert, BODConverter

__all__ = ["to_json", "to_ndjson", "to_records", "project", "convert", "BODConverter"]