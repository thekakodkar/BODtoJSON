"""
BODtoJSON: A zero-dependency OAGIS BOD to Flattened JSON/NDJSON & Schema Projection engine.

XML is parsed with a stdlib-only hardened loader (xml.parsers.expat +
xml.etree.ElementTree). There are no third-party runtime dependencies.
"""

__version__ = "2.4.0"

from .mapper import (
    BODConverter,
    BODParseError,
    BODStructureError,
    convert,
    project,
    to_json,
    to_ndjson,
    to_records,
)

__all__ = [
    "to_json",
    "to_ndjson",
    "to_records",
    "project",
    "convert",
    "BODConverter",
    "BODParseError",
    "BODStructureError",
]
