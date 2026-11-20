"""
JSON to OAGIS BOD XML (the reverse of the flattening pipeline).

Accepts the same flattened records that ``to_json`` / ``to_ndjson`` /
``to_records`` produce, nested JSON objects, or a mix of both, and rebuilds a
BOD envelope::

    <{Verb}{Noun} xmlns="http://schema.infor.com/InforOAGIS/2" releaseID="9.2">
      <ApplicationArea>...</ApplicationArea>
      <DataArea>
        <{Verb}>...</{Verb}>
        <{Noun}>...</{Noun}>   (one per record)
      </DataArea>
    </{Verb}{Noun}>

Flattened key conventions (same as the forward converter, separator ``_``):

* ``A_B_C``            -> ``<A><B><C>value</C></B></A>``
* ``A_B_@attr``        -> attribute ``attr`` on ``<B>``
* ``A_B_#text``        -> text of ``<B>`` (used when ``<B>`` has attributes/children)
* ``A_Line_0_ID``      -> first repeated ``<Line>``; ``A_Line_1_ID`` the second
* first segment ``ApplicationArea`` -> the ``ApplicationArea`` block
* first segment equal to the verb (e.g. ``Sync``) -> the ``DataArea/Sync`` block

Nested input uses the same markers as keys: ``{"@attr": ..}``, ``{"#text": ..}``
and JSON arrays for repeated elements.

Pure standard library: output is written by a small serializer with explicit
escaping, no XML parser is involved.
"""

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Union

from .mapper import BODParseError, BODStructureError
from .transforms import RulesLike, compile_rules

__all__ = ["INFOR_OAGIS_NS", "json_to_bod"]

INFOR_OAGIS_NS = "http://schema.infor.com/InforOAGIS/2"
DEFAULT_MAX_SIZE = 10 * 1024 * 1024
DEFAULT_MAX_DEPTH = 256

_NAME_RE = re.compile(r"^[^\W\d][\w.\-]*$")
_BAD_CHARS_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff\ud800-\udfff]")

JSONInput = Union[str, bytes, Mapping[str, Any], List[Any]]


class _Node:
    __slots__ = ("tag", "attrs", "text", "children")

    def __init__(self, tag: str):
        self.tag = tag
        self.attrs: Dict[str, str] = {}
        self.text: Optional[str] = None
        self.children: Dict[str, Dict[int, _Node]] = {}

    def child(self, tag: str, idx: int = 0) -> "_Node":
        _check_name(tag, "element")
        group = self.children.setdefault(tag, {})
        node = group.get(idx)
        if node is None:
            node = group[idx] = _Node(tag)
        return node

    def ordered_children(self) -> List["_Node"]:
        out: List[_Node] = []
        for group in self.children.values():
            out.extend(group[i] for i in sorted(group))
        return out

    def is_empty(self) -> bool:
        return not self.attrs and self.text is None and not self.children


def _check_name(name: str, kind: str) -> None:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise BODStructureError(f"Invalid XML {kind} name: {name!r}.")


def _scalar_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (int, float, str)):
        text = str(value)
    else:
        raise BODStructureError(f"Unsupported value type {type(value).__name__}.")
    if _BAD_CHARS_RE.search(text):
        raise BODStructureError("Value contains characters that are not allowed in XML 1.0.")
    return text


def _esc_text(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(
        "\r", "&#13;"
    )


def _esc_attr(s: str) -> str:
    return (
        _esc_text(s)
        .replace('"', "&quot;")
        .replace("\n", "&#10;")
        .replace("\t", "&#9;")
    )


class _Builder:
    def __init__(self, separator: str, max_depth: int):
        self.sep = separator
        self.max_depth = max_depth

    # -- flat keys -----------------------------------------------------
    def put_flat(self, container: _Node, key: str, value: Any) -> None:
        if not isinstance(key, str) or not key:
            raise BODStructureError("Record keys must be non-empty strings.")
        segs = key.split(self.sep)
        if len(segs) > self.max_depth:
            raise BODStructureError(f"Key '{key}' is deeper than {self.max_depth} levels.")
        node = container
        i = 0
        while i < len(segs):
            seg = segs[i]
            if seg.startswith("@"):
                if node is container:
                    raise BODStructureError(f"Key '{key}': attribute without an element.")
                name = self.sep.join(segs[i:])[1:]
                _check_name(name, "attribute")
                text = self._value_text(value, key)
                if text is not None:
                    node.attrs[name] = text
                return
            if seg == "#text":
                if node is container or i != len(segs) - 1:
                    raise BODStructureError(f"Key '{key}': misplaced '#text'.")
                node.text = self._value_text(value, key)
                return
            if seg.isdigit():
                raise BODStructureError(f"Key '{key}': index '{seg}' has no element name.")
            idx = 0
            step = 1
            if i + 1 < len(segs) and segs[i + 1].isdigit():
                idx = int(segs[i + 1])
                step = 2
            node = node.child(seg, idx)
            i += step
        self.fill(node, value, 1)

    def _value_text(self, value: Any, key: str) -> Optional[str]:
        if isinstance(value, (dict, list)):
            raise BODStructureError(f"Key '{key}': attributes and text must be scalars.")
        return _scalar_text(value)

    # -- nested values -------------------------------------------------
    def fill(self, node: _Node, value: Any, depth: int) -> None:
        if depth > self.max_depth:
            raise BODStructureError(f"Input nesting exceeds {self.max_depth} levels.")
        if isinstance(value, Mapping):
            for k, v in value.items():
                self.put_nested(node, k, v, depth + 1)
        elif isinstance(value, list):
            raise BODStructureError(f"Element '{node.tag}': unexpected nested list.")
        else:
            node.text = _scalar_text(value)

    def put_nested(self, node: _Node, key: Any, value: Any, depth: int) -> None:
        if not isinstance(key, str) or not key:
            raise BODStructureError("Object keys must be non-empty strings.")
        if key.startswith("@"):
            _check_name(key[1:], "attribute")
            text = self._value_text(value, key)
            if text is not None:
                node.attrs[key[1:]] = text
            return
        if key == "#text":
            node.text = self._value_text(value, key)
            return
        if isinstance(value, list):
            group = node.children.get(key, {})
            start = max(group) + 1 if group else 0
            for offset, item in enumerate(value):
                self.fill(node.child(key, start + offset), item, depth + 1)
            if not value:
                node.child(key, start)
            return
        self.fill(node.child(key, 0), value, depth + 1)

    # -- serialization -------------------------------------------------
    def serialize(self, node: _Node, pretty: bool, ns: Optional[str], root: bool) -> str:
        lines: List[str] = []
        self._write(node, 0, lines, pretty, ns if root else None)
        return ("\n" if pretty else "").join(lines)

    def _write(
        self, node: _Node, level: int, lines: List[str], pretty: bool, ns: Optional[str]
    ) -> None:
        pad = "  " * level if pretty else ""
        attrs = ""
        if ns:
            attrs += f' xmlns="{_esc_attr(ns)}"'
        for k, v in node.attrs.items():
            attrs += f' {k}="{_esc_attr(v)}"'
        children = node.ordered_children()
        if not children:
            if node.text is None:
                lines.append(f"{pad}<{node.tag}{attrs}/>")
            else:
                lines.append(f"{pad}<{node.tag}{attrs}>{_esc_text(node.text)}</{node.tag}>")
            return
        text = _esc_text(node.text) if node.text is not None else ""
        lines.append(f"{pad}<{node.tag}{attrs}>{text}")
        for c in children:
            self._write(c, level + 1, lines, pretty, None)
        lines.append(f"{pad}</{node.tag}>")


def _load_records(data: JSONInput, max_size: int) -> List[Dict[str, Any]]:
    obj: Any
    if isinstance(data, (bytes, bytearray, memoryview)):
        if len(data) > max_size:
            raise BODParseError(f"Input exceeds maximum allowed size of {max_size} bytes.")
        try:
            data = bytes(data).decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise BODParseError(f"Input is not valid UTF-8: {e}") from e
    if isinstance(data, str):
        if len(data.encode("utf-8", "surrogatepass")) > max_size:
            raise BODParseError(f"Input exceeds maximum allowed size of {max_size} bytes.")
        text = data.strip().lstrip("\ufeff")
        if not text:
            raise BODParseError("Input JSON is empty.")
        try:
            obj = json.loads(text)
        except RecursionError as e:
            raise BODParseError("Input JSON is nested too deeply.") from e
        except ValueError:
            try:
                obj = [json.loads(line) for line in text.splitlines() if line.strip()]
            except RecursionError as e:
                raise BODParseError("Input JSON is nested too deeply.") from e
            except ValueError as e:
                raise BODParseError(f"Input is neither JSON nor NDJSON: {e}") from e
    else:
        obj = data

    if isinstance(obj, Mapping):
        if set(obj) == {"status", "message"} and obj.get("status") == "error":
            raise BODStructureError(f"Input is an error object: {obj.get('message')}")
        records = [obj]
    elif isinstance(obj, list):
        records = obj
    else:
        raise BODStructureError("Input must be a JSON object, an array of objects, or NDJSON.")
    if not records:
        raise BODStructureError("Input contains no records.")
    for r in records:
        if not isinstance(r, Mapping):
            raise BODStructureError("Every record must be a JSON object.")
    return [dict(r) for r in records]


def _is_flat(record: Mapping[str, Any]) -> bool:
    return all(not isinstance(v, (dict, list)) for v in record.values())


def _flatten_nested(
    obj: Mapping[str, Any], sep: str, max_depth: int, prefix: str = "", depth: int = 0
) -> Dict[str, Any]:
    if depth > max_depth:
        raise BODStructureError(f"Input nesting exceeds {max_depth} levels.")
    out: Dict[str, Any] = {}
    for k, v in obj.items():
        key = f"{prefix}{sep}{k}" if prefix else str(k)
        if isinstance(v, Mapping):
            out.update(_flatten_nested(v, sep, max_depth, key, depth + 1))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                ik = f"{key}{sep}{i}"
                if isinstance(item, Mapping):
                    out.update(_flatten_nested(item, sep, max_depth, ik, depth + 1))
                elif isinstance(item, list):
                    raise BODStructureError(f"'{key}': nested lists are not supported.")
                else:
                    out[ik] = item
        else:
            out[key] = v
    return out


def json_to_bod(
    data: JSONInput,
    verb: str = "Sync",
    noun: Optional[str] = None,
    *,
    rules: Optional[RulesLike] = None,
    separator: str = "_",
    namespace: Optional[str] = INFOR_OAGIS_NS,
    root: Optional[str] = None,
    release_id: Optional[str] = "9.2",
    version_id: Optional[str] = None,
    application_area: Optional[Mapping[str, Any]] = None,
    include_application_area: bool = True,
    action_code: Optional[str] = None,
    flat: Optional[bool] = None,
    pretty: bool = True,
    xml_declaration: bool = True,
    max_size: int = DEFAULT_MAX_SIZE,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> str:
    """Build an OAGIS BOD XML string from JSON.

    Args:
        data: JSON text, NDJSON text, bytes, a dict (one record) or a list of
            dicts (one noun per record). Records may be flattened (the output
            of ``to_json`` / ``to_records``), nested objects, or a mix.
        verb: verb element name under ``DataArea`` (default ``"Sync"``).
        noun: noun element name. When given, record keys that do not already
            start with the noun, ``ApplicationArea`` or the verb are placed
            under the noun, so keys can be written relative to it.
        rules: optional transformation rules applied to each record (after
            nested input is flattened) before XML is built. Defaults to
            ``mode: "only"`` so the rule targets are the BOD paths to emit.
        separator: flattened-key separator (default ``"_"``).
        namespace: default namespace on the root (``None`` to omit).
        root: root element name (default ``verb + noun``, e.g. ``SyncPurchaseOrder``).
        release_id / version_id: root ``releaseID`` / ``versionID`` attributes
            (``None`` to omit).
        application_area: extra ApplicationArea content (flat keys relative to
            ApplicationArea, keys starting with ``ApplicationArea``, or nested).
        include_application_area: when no ApplicationArea data is provided,
            generate one with ``CreationDateTime`` (UTC). ``False`` omits it.
        action_code: adds ``ActionCriteria/ActionExpression/@actionCode`` to
            the verb unless the input already provides it.
        flat: force flattened (``True``) or nested (``False``) key handling;
            ``None`` auto-detects per record (all scalar values = flattened).
        pretty: indent output with two spaces.
        xml_declaration: prefix ``<?xml version="1.0" encoding="UTF-8"?>``.

    Raises:
        BODParseError: invalid JSON / oversize input.
        BODStructureError: input cannot be expressed as a BOD (bad names, no noun...).
        BODTransformError: invalid rules.
    """
    if not separator:
        raise BODStructureError("Separator must be a non-empty string.")
    _check_name(verb, "verb")
    if noun is not None:
        _check_name(noun, "noun")
    if root is not None:
        _check_name(root, "root")

    records = _load_records(data, max_size)
    compiled = (
        compile_rules(rules, separator=separator, default_mode="only")
        if rules is not None
        else None
    )
    builder = _Builder(separator, max_depth)
    specials = {"ApplicationArea", verb}

    app_node: Optional[_Node] = None
    verb_node: Optional[_Node] = None
    nouns: List[_Node] = []

    for record in records:
        is_flat = _is_flat(record) if flat is None else flat
        if compiled is not None:
            if not is_flat:
                record = _flatten_nested(record, separator, max_depth)
            record = compiled.apply(record)
            is_flat = True

        container = _Node("#record")
        for key, value in record.items():
            if is_flat:
                first = key.split(separator, 1)[0] if isinstance(key, str) else key
                if noun is not None and first not in specials and first != noun:
                    key = f"{noun}{separator}{key}"
                builder.put_flat(container, key, value)
            elif noun is not None and key not in specials and key != noun:
                builder.put_nested(container.child(noun, 0), key, value, 1)
            else:
                builder.put_nested(container, key, value, 1)

        for child in container.ordered_children():
            if child.tag == "ApplicationArea":
                app_node = app_node or child
            elif child.tag == verb:
                verb_node = verb_node or child
            else:
                nouns.append(child)

    if not nouns:
        raise BODStructureError("No noun data found in the input.")

    if application_area:
        app_node = app_node or _Node("ApplicationArea")
        holder = _Node("#app")
        holder.children["ApplicationArea"] = {0: app_node}
        if _is_flat(application_area):
            for key, value in application_area.items():
                if not str(key).startswith("ApplicationArea"):
                    key = f"ApplicationArea{separator}{key}"
                builder.put_flat(holder, key, value)
        else:
            payload = application_area.get("ApplicationArea", application_area)
            builder.fill(app_node, payload, 1)
    if app_node is None and include_application_area:
        app_node = _Node("ApplicationArea")
        app_node.child("CreationDateTime").text = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    verb_node = verb_node or _Node(verb)
    if action_code is not None:
        expr = verb_node.child("ActionCriteria").child("ActionExpression")
        if "actionCode" not in expr.attrs:
            text = _scalar_text(action_code)
            if text is not None:
                expr.attrs["actionCode"] = text

    root_node = _Node(root or f"{verb}{nouns[0].tag}")
    _check_name(root_node.tag, "root")
    if release_id is not None:
        root_node.attrs["releaseID"] = _scalar_text(release_id) or ""
    if version_id is not None:
        root_node.attrs["versionID"] = _scalar_text(version_id) or ""
    if app_node is not None:
        root_node.children["ApplicationArea"] = {0: app_node}
    data_area = root_node.child("DataArea")
    data_area.children[verb] = {0: verb_node}
    seen: Dict[str, int] = {}
    for n in nouns:
        idx = seen.get(n.tag, 0)
        data_area.children.setdefault(n.tag, {})[idx] = n
        seen[n.tag] = idx + 1

    body = builder.serialize(root_node, pretty, namespace, root=True)
    if xml_declaration:
        return '<?xml version="1.0" encoding="UTF-8"?>' + ("\n" if pretty else "") + body + (
            "\n" if pretty else ""
        )
    return body + ("\n" if pretty else "")

