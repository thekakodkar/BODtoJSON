"""
BODtoJSON: A zero-dependency OAGIS BOD to Flattened JSON/NDJSON & Schema Projection engine.

XML is parsed with a stdlib-only hardened loader (xml.parsers.expat +
xml.etree.ElementTree). There are no third-party runtime dependencies.

2.5.0 added declarative transformation rules (if/else, case, concat, template,
...) applied to flattened records, and the reverse JSON -> BOD XML builder.
2.6.0 adds one-call mapping to your own nested JSON shape:

    from BODtoJSON import bod_to_json
    output_var = bod_to_json(input_var, rules=RULES)
"""

__version__ = "2.6.0"

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
from .mapping import Mapper, bod_to_data, bod_to_json
from .reverse import INFOR_OAGIS_NS, json_to_bod
from .transforms import BODTransformError, TransformRules, apply_rules, compile_rules

__all__ = [
    "bod_to_json",
    "bod_to_data",
    "Mapper",
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
