"""
Command-line interface (stdlib ``argparse`` only).

Examples::

    bodtojson to-json order.xml --verb Sync --rules rules.json
    bodtojson to-json order.xml --format ndjson --include-header
    bodtojson to-bod order.json --verb Sync --noun PurchaseOrder --action-code Replace
    python -m BODtoJSON to-bod - < records.ndjson > order.xml

Exit codes: 0 success, 2 usage error, 1 conversion error (message on stderr).
"""

import argparse
import json
import sys
from typing import List, Optional

from . import __version__
from .mapper import BODConverter, BODParseError, BODStructureError
from .reverse import INFOR_OAGIS_NS
from .transforms import BODTransformError


def _read(path: str) -> bytes:
    if path == "-":
        return sys.stdin.buffer.read()
    with open(path, "rb") as f:
        return f.read()


def _write(path: Optional[str], text: str) -> None:
    if not path or path == "-":
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
        return
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _load_rules(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return _read(path).decode("utf-8-sig")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bodtojson",
        description="Convert OAGIS BOD XML to flattened JSON (with optional rules) and back.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    fwd = sub.add_parser("to-json", help="BOD XML -> flattened JSON / NDJSON / records")
    fwd.add_argument("input", help="XML file path, or - for stdin")
    fwd.add_argument("--verb", default="Sync", help="Verb element under DataArea (default Sync)")
    fwd.add_argument(
        "--format",
        choices=("json", "ndjson", "records"),
        default="json",
        help="json = first noun object; ndjson = one line per noun; records = JSON array",
    )
    fwd.add_argument("--rules", help="Transformation rules JSON file")
    fwd.add_argument(
        "--include-header",
        action="store_true",
        help="Merge ApplicationArea and verb fields into each record (ndjson/records)",
    )
    fwd.add_argument("--separator", default="_", help="Key separator (default _)")
    fwd.add_argument("--indent", type=int, default=None, help="Pretty-print JSON")
    fwd.add_argument("-o", "--output", help="Output file (default stdout)")

    rev = sub.add_parser("to-bod", help="JSON / NDJSON -> BOD XML")
    rev.add_argument("input", help="JSON or NDJSON file path, or - for stdin")
    rev.add_argument("--verb", default="Sync", help="Verb element (default Sync)")
    rev.add_argument("--noun", help="Noun element; keys not starting with it are placed under it")
    rev.add_argument("--rules", help="Transformation rules JSON file (default mode: only)")
    rev.add_argument("--root", help="Root element name (default <Verb><Noun>)")
    rev.add_argument(
        "--namespace",
        default=INFOR_OAGIS_NS,
        help="Default namespace; pass an empty string to omit",
    )
    rev.add_argument("--release-id", default="9.2", help="releaseID attribute ('' to omit)")
    rev.add_argument("--version-id", default=None, help="versionID attribute")
    rev.add_argument("--action-code", help="Add ActionCriteria/ActionExpression/@actionCode")
    rev.add_argument(
        "--no-application-area",
        action="store_true",
        help="Do not generate an ApplicationArea when the input has none",
    )
    rev.add_argument("--separator", default="_", help="Key separator (default _)")
    rev.add_argument("--compact", action="store_true", help="No indentation")
    rev.add_argument("-o", "--output", help="Output file (default stdout)")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        conv = BODConverter(separator=args.separator)
        rules = _load_rules(args.rules)
        data = _read(args.input)
        if args.command == "to-json":
            if args.format == "json":
                text = conv.to_json(data, args.verb, raise_on_error=True, rules=rules)
                if args.indent is not None:
                    text = json.dumps(json.loads(text), indent=args.indent)
            elif args.format == "ndjson":
                text = conv.to_ndjson(
                    data,
                    args.verb,
                    raise_on_error=True,
                    rules=rules,
                    include_header=args.include_header,
                )
            else:
                recs = conv.to_records(
                    data, args.verb, include_header=args.include_header, rules=rules
                )
                text = json.dumps(recs, indent=args.indent)
        else:
            text = conv.from_json(
                data,
                args.verb,
                args.noun,
                rules=rules,
                root=args.root,
                namespace=args.namespace or None,
                release_id=args.release_id or None,
                version_id=args.version_id or None,
                action_code=args.action_code,
                include_application_area=not args.no_application_area,
                pretty=not args.compact,
            )
        _write(args.output, text)
        return 0
    except (BODParseError, BODStructureError, BODTransformError, OSError) as e:
        sys.stderr.write(f"bodtojson: error: {e}\n")
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
