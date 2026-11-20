"""
BODtoJSON: A zero-dependency OAGIS BOD to Flattened JSON/NDJSON & Schema Projection engine.

XML is parsed with a stdlib-only hardened loader (xml.parsers.expat +
xml.etree.ElementTree). There are no third-party runtime dependencies.

2.5.0 adds declarative transformation rules (if/else, case, concat, template,
...) applied to flattened records, and the reverse JSON -> BOD XML builder.
"""

__version__ = "2.5.0"

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
from .reverse import INFOR_OAGIS_NS, json_to_bod
from .transforms import BODTransformError, TransformRules, apply_rules, compile_rules

__all__ = [
    "to_json",
    "to_ndjson",
    "to_records",
    "project",
    "convert",
    "json_to_bod",
    "apply_rules",
    "compile_rules",
    "TransformRules",
    "BODConverter",
    "BODParseError",
    "BODStructureError",
    "BODTransformError",
    "INFOR_OAGIS_NS",
]
