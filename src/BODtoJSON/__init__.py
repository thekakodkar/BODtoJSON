"""
BODtoJSON: Safe OAGIS BOD to Flattened JSON/NDJSON & Schema Projection engine.

Depends on defusedxml for secure XML parsing.
"""

__version__ = "2.3.1"

from .mapper import (
    to_json,
    to_ndjson,
    to_records,
    project,
    convert,
    BODConverter,
    BODParseError,
    BODStructureError,
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
