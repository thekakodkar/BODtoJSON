"""Stdlib-only hardened XML loader.

Stdlib-only hardened XML loader for BODtoJSON (Infor ION, air-gapped hosts).

Defense in depth:
  1. Decode from bytes with BOM + XML-declaration encoding detection,
     also scanning raw bytes in UTF-8/16/32 so a UTF-16 DOCTYPE cannot
     slip past a UTF-8-only search.
  2. Reject any DOCTYPE or ENTITY declaration in the decoded text
     (case-insensitive). OAGIS BODs do not need DTDs. This is the
     portable guarantee on older expat (< 2.4.1) that lacks built-in
     billion-laughs protection.
  3. Parse with xml.parsers.expat + ElementTree.TreeBuilder, never
     xml.etree.ElementTree.fromstring. Handlers raise on DTD, entity
     declarations, and external entity references. Parameter entity
     parsing is disabled. Reparse deferral is enabled when present.
  4. Configurable input-size and max-element-depth limits.

Python/expat notes (this box: Python 3.13.5, expat 2.9.0):
  - Expat >= 2.4.1 added billion-laughs protection; Python may or may
    not wrap SetBillionLaughsProtection (it is NOT exposed on 3.13's
    pyexpat parser object here). Do not rely on it.
  - Expat 2.4.0+ reparse deferral is exposed as
    SetReparseDeferralEnabled / GetReparseDeferralEnabled; we turn it on
    when available. Older 3.8 runtimes may lack these methods.
  - Because of that variance, the pre-parse DOCTYPE/ENTITY rejection is
    the compatibility guarantee; the expat handlers are a second line.
"""
from __future__ import annotations

import codecs
import re
from typing import Union
from xml.etree.ElementTree import Element, ParseError, TreeBuilder
from xml.parsers import expat

# XML names are case-sensitive; <!DOCTYPE> must be that exact token.
# We still reject case-insensitively as defense in depth.
_FORBIDDEN_RE = re.compile(r"<!DOCTYPE|<!ENTITY", re.IGNORECASE)

_UTF_BOMS = (
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
    (codecs.BOM_UTF8, "utf-8-sig"),
)

# XML declaration encoding capture, ASCII-compatible encodings only.
_DECL_ENCODING_RE = re.compile(
    br"""<\?xml\s+[^>]*encoding\s*=\s*['"]([A-Za-z0-9._-]+)['"]""",
    re.IGNORECASE,
)


class SafeXMLError(ValueError):
    """Input is not accepted by the hardened stdlib parser."""


def _encode_needles(text: str, encoding: str) -> list:
    try:
        return [text.encode(encoding)]
    except LookupError:
        return []


def _raw_contains_forbidden(raw: bytes) -> bool:
    """Byte-level search in common XML encodings, with and without BOM."""
    tokens = ("<!DOCTYPE", "<!ENTITY", "<!doctype", "<!entity", "<!Doctype", "<!Entity")
    encodings = (
        "utf-8",
        "utf-16-le",
        "utf-16-be",
        "utf-32-le",
        "utf-32-be",
        "utf-16",
        "latin-1",
    )
    haystacks = [raw]
    for bom, _enc in _UTF_BOMS:
        if raw.startswith(bom):
            haystacks.append(raw[len(bom):])
    for hay in haystacks:
        for enc in encodings:
            for tok in tokens:
                for needle in _encode_needles(tok, enc):
                    if needle and needle in hay:
                        return True
    return False


def _detect_encoding(raw: bytes) -> str:
    for bom, enc in _UTF_BOMS:
        if raw.startswith(bom):
            return enc
    # UTF-16/32 without BOM: NUL patterns in the XML declaration
    if len(raw) >= 4:
        if raw[0:4] in (b"<\x00\x00\x00", b"\x00\x00\x00<"):
            return "utf-32-le" if raw[0] == 0x3C else "utf-32-be"
        if raw[0:2] == b"<\x00":
            return "utf-16-le"
        if raw[0:2] == b"\x00<":
            return "utf-16-be"
    # ASCII-compatible declaration
    head = raw[:200].lstrip()
    # Also try utf-16 declaration without BOM already handled
    m = _DECL_ENCODING_RE.search(head)
    if m:
        enc = m.group(1).decode("ascii", "ignore")
        if enc:
            return enc
    return "utf-8"


def _decode(raw: bytes) -> str:
    enc = _detect_encoding(raw)
    try:
        return raw.decode(enc)
    except UnicodeError as e:
        raise SafeXMLError(f"Unable to decode XML as {enc}: {e}") from e


def _scan_text(text: str) -> None:
    if _FORBIDDEN_RE.search(text):
        raise SafeXMLError(
            "DOCTYPE and ENTITY declarations are not allowed "
            "(rejected before parse)."
        )


def _clark(name: str) -> str:
    """Convert expat 'uri}local' names to ElementTree '{uri}local'."""
    if "}" in name and not name.startswith("{"):
        return "{" + name
    return name


def _fix_attrs(attrs: dict) -> dict:
    return {_clark(k): v for k, v in attrs.items()}


def parse_xml(
    source: Union[str, bytes],
    *,
    max_size: int = 10 * 1024 * 1024,
    max_depth: int = 256,
) -> Element:
    """Parse XML into an ElementTree element using only the stdlib.

    Raises SafeXMLError for oversize input, DTD/entity declarations,
    external entities, or depth-limit violations. Other well-formedness
    errors are raised as xml.etree.ElementTree.ParseError (or SafeXMLError
    wrapping expat errors).
    """
    if isinstance(source, str):
        if source.startswith("\ufeff"):
            source = source.lstrip("\ufeff")
        text = source
        raw = source.encode("utf-8")
        # If the caller passed a UTF-8 string we're good; also scan the
        # text itself. The byte scan still runs on the UTF-8 encoding.
    else:
        raw = source
        if _raw_contains_forbidden(raw):
            raise SafeXMLError(
                "DOCTYPE and ENTITY declarations are not allowed "
                "(detected in raw bytes)."
            )
        text = _decode(raw)

    if len(raw) > max_size:
        raise SafeXMLError(
            f"Document exceeds maximum allowed size of {max_size} bytes."
        )

    _scan_text(text)
    return _expat_parse(text, max_depth=max_depth)


def _expat_parse(text: str, max_depth: int = 256) -> Element:
    """Parse already-decoded text with a locked-down expat parser.

    The pre-scan in parse_xml is the portable guarantee. This function is
    the second line of defense and is also used in tests to prove the
    handlers reject DTD/entity constructs if they ever reach expat.
    """
    builder = TreeBuilder()
    # namespace_separator='}' yields "uri}local" which we map to Clark form.
    parser = expat.ParserCreate(namespace_separator="}")
    parser.buffer_text = True
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    if hasattr(parser, "SetReparseDeferralEnabled"):
        parser.SetReparseDeferralEnabled(True)

    depth = 0

    def start(tag, attrs):
        nonlocal depth
        depth += 1
        if depth > max_depth:
            raise SafeXMLError(
                f"XML element depth exceeds maximum of {max_depth}."
            )
        builder.start(_clark(tag), _fix_attrs(attrs))

    def end(tag):
        nonlocal depth
        builder.end(_clark(tag))
        depth -= 1

    def data(chunk):
        builder.data(chunk)

    def forbid_dtd(*_args):
        raise SafeXMLError("DOCTYPE declarations are not allowed.")

    def forbid_entity(*_args):
        raise SafeXMLError("Entity declarations are not allowed.")

    def forbid_ext_ref(*_args):
        raise SafeXMLError("External entity references are not allowed.")

    def forbid_skipped(*_args):
        raise SafeXMLError("Entity references are not allowed.")

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = data
    parser.StartDoctypeDeclHandler = forbid_dtd
    parser.EndDoctypeDeclHandler = forbid_dtd
    parser.EntityDeclHandler = forbid_entity
    parser.UnparsedEntityDeclHandler = forbid_entity
    parser.ExternalEntityRefHandler = forbid_ext_ref
    if hasattr(parser, "SkippedEntityHandler"):
        parser.SkippedEntityHandler = forbid_skipped

    try:
        parser.Parse(text, True)
        return builder.close()
    except SafeXMLError:
        raise
    except expat.ExpatError as e:
        raise ParseError(f"{e}") from e


# Public alias used by the converter.
fromstring = parse_xml
