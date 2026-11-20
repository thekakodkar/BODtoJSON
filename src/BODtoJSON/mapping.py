"""
One-call mapping from a BOD to *your* JSON shape.

    from BODtoJSON import bod_to_json
    output_var = bod_to_json(input_var, rules=RULES)

``RULES`` is an output template: write the JSON you want, and put a BOD field
path wherever a value should come from the document. Every noun under
``DataArea`` becomes one output object (a JSON array by default). Header fields
(``ApplicationArea_*`` and ``<Verb>_*``, e.g. ``Sync_AccountingEntityID``)
are available everywhere, including inside repeated lines.

Template values
    ``"Path_To_Field"``          value of that flattened field (``_#text`` fallback;
                                 a leading ``$`` or ``{...}`` around the path is optional)
    ``"text {A}_{B}"``           a string with ``{path}`` placeholders is a template
    ``true`` / ``1`` / ``null``  literals; ``{}`` / ``[]`` / ``[{}]`` pass through
    ``{...}`` / ``[...]``        nested output shape (evaluated recursively)
    ``{"literal": x}``           x unchanged (use for constant text)
    ``{"template": "..."}``      explicit template (no braces = constant text)
    ``{"path": "P", "default": d}``
    ``{"repeat": "Prefix_*", "item": {...}, "where": cond}``  one item per repeated element
    ``{"if": cond, "then": x, "else": y}`` / ``{"if": [{"when": c, "then": x}, ...], "else": y}``
    ``{"case": [{"when": cond, "then": x}, ...], "default": y}``
    ``{"case": "Path", "when": {"A": x, "B": y}, "default": z}``
    ``{"concat": [x, y, ...], "sep": ""}``, ``{"coalesce": [x, y]}``
    ``{"upper": x}``, ``{"lower": x}``, ``{"trim": x}``, ``{"number": x, "default": d}``
    ``{"replace": x, "old": "a", "new": "b"}``, ``{"substr": x, "start": 0, "end": 3}``

Plain strings in output fields are always paths (missing -> ``missing``).
In operator arguments and results (``then``/``else``/``default``/``when``
values, ``concat``/``coalesce`` items) a plain string is a path when the field
exists or the string looks like a path (contains ``_``, ``@``, ``#`` or ``*``);
otherwise it is literal text, so ``"then": "high"`` and ``["PO-", "Path"]``
work. ``{"literal": "text"}`` is always literal.

Conditions (both forms are accepted)
    ``{"eq": ["Path", "value"]}``                 compact
    ``{"path": "Path", "op": "eq", "value": "value"}``
    ops: eq ne gt ge lt le in not_in contains not_contains starts_with ends_with
    exists missing empty not_empty; ``{"all": [...]}``, ``{"any": [...]}``,
    ``{"not": c}``; a bare ``"Path"`` is true when the field is not empty.
    The compared value is a literal; write ``"$Path"`` to compare with another field.

Repeated elements
    ``"repeat": "PurchaseOrder_PurchaseOrderLine_*"`` yields one item per line
    (a single unindexed line works too, no lines gives ``[]``). Inside ``item``
    a ``*`` in a path is the current line, and paths may also be written
    relative to the line (``"LineNumber"``). A nested repeat such as
    ``"CodingLine_*"`` is relative to the current line.

No ``eval``/``exec``: the template is validated once and then interpreted.
"""

import json
import os
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

from .mapper import BODConverter
from .transforms import (
    _COND_KEYS,
    _OP_ALIASES,
    _OPS,
    _UNARY_OPS,
    BODTransformError,
    TransformRules,
    _is_empty,
    _to_number,
    _to_text,
    compare,
    normalize_op,
)

__all__ = ["Mapper", "bod_to_json", "bod_to_data", "is_template_rules"]

MAX_TEMPLATE_DEPTH = 128

# operator -> allowed companion keys
_TEMPLATE_OPS: Dict[str, set] = {
    "repeat": {"item", "where"},
    "if": {"then", "else"},
    "case": {"when", "default", "ignore_case"},
    "concat": {"sep", "skip_empty"},
    "template": set(),
    "coalesce": set(),
    "upper": set(),
    "lower": set(),
    "trim": set(),
    "number": {"default"},
    "replace": {"old", "new"},
    "substr": {"start", "end"},
    "literal": set(),
    "path": {"default"},
}
_PLACEHOLDER_RE = re.compile(r"\{\{|\}\}|\{([^{}]+)\}")
_LEGACY_WRAPPER_KEYS = {"rules", "mode", "drop", "description", "version"}

RulesInput = Union[Mapping[str, Any], str, bytes, "os.PathLike[str]"]


def _template_op(node: Mapping[str, Any]) -> Optional[str]:
    """Return the operator if ``node`` is an expression, else None (output shape)."""
    for op, extra in _TEMPLATE_OPS.items():
        if op in node and set(node) <= {op} | extra:
            return op
    return None


def _clean_path(path: str) -> str:
    path = path.strip()
    if path.startswith("{") and path.endswith("}") and not path.startswith("{{"):
        path = path[1:-1].strip()
    if path.startswith("$"):
        path = path[1:]
    return path


def load_rules(rules: RulesInput) -> Any:
    """Accept a dict, JSON text, bytes, or a path to a JSON file."""
    if isinstance(rules, (bytes, bytearray)):
        rules = bytes(rules).decode("utf-8-sig")
    if isinstance(rules, os.PathLike):
        rules = os.fspath(rules)
    if isinstance(rules, str):
        text = rules.strip().lstrip("\ufeff")
        if not text.startswith(("{", "[")):
            if not os.path.isfile(text):
                raise BODTransformError(
                    "Rules must be a dict, JSON text, or an existing file path "
                    f"(got {text[:80]!r})."
                )
            with open(text, encoding="utf-8-sig") as f:
                text = f.read()
        try:
            return json.loads(text)
        except (ValueError, RecursionError) as e:
            raise BODTransformError(f"Rules are not valid JSON: {e}") from e
    return rules


def is_template_rules(rules: Any) -> bool:
    """True for an output template, False for 2.5-style flat rules.

    Flat rules are the ``{"rules": {...}, "mode": ...}`` wrapper, or a flat object
    whose string values are all ``"$Path"`` references (no plain path strings,
    no lists, no nested output objects).
    """
    if not isinstance(rules, Mapping):
        return True
    if isinstance(rules.get("rules"), Mapping) and set(rules) <= _LEGACY_WRAPPER_KEYS:
        return False
    saw_dollar = False
    for value in rules.values():
        if isinstance(value, str):
            if not value.startswith("$"):
                return True
            saw_dollar = True
        elif isinstance(value, list):
            return True
        elif isinstance(value, Mapping):
            if _template_op(value) is None or "repeat" in value:
                return True
            if _mentions_dollar(value):
                saw_dollar = True
            elif _has_plain_path(value):
                return True
    if not saw_dollar:
        return True
    try:  # only treat as flat rules if they are valid flat rules
        TransformRules(rules)
    except BODTransformError:
        return True
    return False


def _mentions_dollar(node: Any) -> bool:
    if isinstance(node, str):
        return node.startswith("$")
    if isinstance(node, Mapping):
        return any(_mentions_dollar(v) for v in node.values())
    if isinstance(node, list):
        return any(_mentions_dollar(v) for v in node)
    return False


def _has_plain_path(node: Mapping[str, Any]) -> bool:
    op = _template_op(node)
    if op in ("upper", "lower", "trim", "number", "replace", "substr"):
        arg = node[op]
        return isinstance(arg, str) and not arg.startswith("$")
    if op in ("concat", "coalesce"):
        return any(isinstance(a, str) and not a.startswith("$") for a in node[op])
    return False


class _Frame:
    __slots__ = ("prefix", "binding")

    def __init__(self, prefix: str, binding: Optional[str]):
        self.prefix = prefix
        self.binding = binding


class _Ctx:
    __slots__ = ("record", "roots", "frames")

    def __init__(self, record: Mapping[str, Any], roots: set, frames: Tuple[_Frame, ...]):
        self.record = record
        self.roots = roots
        self.frames = frames

    def push(self, frame: _Frame) -> "_Ctx":
        return _Ctx(self.record, self.roots, self.frames + (frame,))


class Mapper:
    """Compile an output template (or 2.5 flat rules) once and map many BODs.

    Args:
        rules: dict, JSON text, or a path to a JSON file.
        kind: ``"auto"`` (default), ``"template"`` or ``"flat"``.
        missing: value used when a path is not in the document (default ``None``
            -> JSON ``null``; use ``""`` for empty strings).
        separator: flattening separator (default ``"_"``).
    """

    def __init__(
        self,
        rules: RulesInput,
        *,
        kind: str = "auto",
        missing: Any = None,
        separator: str = "_",
    ):
        if kind not in ("auto", "template", "flat"):
            raise BODTransformError("kind must be 'auto', 'template' or 'flat'.")
        if not separator:
            raise BODTransformError("Separator must be a non-empty string.")
        cfg = load_rules(rules)
        self.separator = separator
        self.missing = missing
        if kind == "auto":
            kind = "template" if is_template_rules(cfg) else "flat"
        self.kind = kind
        self._flat: Optional[TransformRules] = None
        if kind == "flat":
            self._flat = TransformRules(cfg, separator=separator)
        else:
            self._validate(cfg, "$", 0)
        self.template = cfg

    @classmethod
    def from_file(cls, path: Union[str, "os.PathLike[str]"], **kwargs: Any) -> "Mapper":
        with open(os.fspath(path), encoding="utf-8-sig") as f:
            return cls(f.read(), **kwargs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def apply(self, record: Mapping[str, Any]) -> Any:
        """Map one flattened record (as produced by ``to_records``)."""
        if not isinstance(record, Mapping):
            raise BODTransformError("Each record must be a dict.")
        if self._flat is not None:
            return self._flat.apply(record)
        sep = self.separator
        roots = {k.split(sep, 1)[0] for k in record if isinstance(k, str)}
        return self._eval(self.template, _Ctx(record, roots, ()))

    def to_data(
        self,
        bod_xml: Union[str, bytes],
        verb: Optional[str] = None,
        *,
        single: bool = False,
        include_header: bool = True,
        converter: Optional[BODConverter] = None,
    ) -> Any:
        """Map a BOD to Python objects: a list (one item per noun) or, with
        ``single=True``, the first noun's object."""
        conv = converter or BODConverter(separator=self.separator)
        records = conv.to_records(bod_xml, verb, include_header=include_header)
        if single:
            return self.apply(records[0])
        return [self.apply(r) for r in records]

    def to_json(
        self,
        bod_xml: Union[str, bytes],
        verb: Optional[str] = None,
        *,
        single: bool = False,
        include_header: bool = True,
        indent: Optional[int] = None,
        converter: Optional[BODConverter] = None,
    ) -> str:
        """Same as :meth:`to_data` but returns a JSON string."""
        data = self.to_data(
            bod_xml, verb, single=single, include_header=include_header, converter=converter
        )
        return json.dumps(data, indent=indent, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Validation (once, with the location of the problem)
    # ------------------------------------------------------------------
    def _err(self, loc: str, msg: str) -> BODTransformError:
        return BODTransformError(f"Rule at '{loc}': {msg}")

    def _validate_path(self, path: Any, loc: str) -> None:
        if not isinstance(path, str) or not _clean_path(path):
            raise self._err(loc, "a path must be a non-empty string.")
        for seg in _clean_path(path).split(self.separator):
            if "*" in seg and seg != "*":
                raise self._err(
                    loc,
                    f"'*' must be a whole path segment in {path!r} "
                    f"(e.g. Line{self.separator}*).",
                )

    def _validate(self, node: Any, loc: str, depth: int) -> None:
        if depth > MAX_TEMPLATE_DEPTH:
            raise self._err(loc, f"template nesting deeper than {MAX_TEMPLATE_DEPTH}.")
        if node is None or isinstance(node, (bool, int, float)):
            return
        if isinstance(node, str):
            if _PLACEHOLDER_RE.search(node):
                for m in _PLACEHOLDER_RE.finditer(node):
                    if m.group(1) is not None:
                        self._validate_path(m.group(1), loc)
            elif node.strip():
                self._validate_path(node, loc)
            return
        if isinstance(node, list):
            for i, item in enumerate(node):
                self._validate(item, f"{loc}[{i}]", depth + 1)
            return
        if not isinstance(node, Mapping):
            raise self._err(loc, f"unsupported value type {type(node).__name__}.")
        op = _template_op(node)
        if op is None:
            for k, v in node.items():
                if not isinstance(k, str):
                    raise self._err(loc, "object keys must be strings.")
                self._validate(v, f"{loc}.{k}", depth + 1)
            return

        arg = node[op]
        nxt = depth + 1
        here = f"{loc}.{op}"
        if op == "repeat":
            self._validate_path(arg, here)
            segs = _clean_path(arg).split(self.separator)
            if segs[-1] != "*" or len(segs) < 2:
                raise self._err(
                    here, f"repeat pattern must end with '{self.separator}*' (got {arg!r})."
                )
            self._validate(node.get("item", {}), f"{loc}.item", nxt)
            if "where" in node:
                self._validate_cond(node["where"], f"{loc}.where", nxt)
        elif op == "if":
            if isinstance(arg, list):
                self._validate_branches(arg, here, nxt)
                if "then" in node:
                    raise self._err(loc, "use 'then' inside each branch of a list 'if'.")
            else:
                self._validate_cond(arg, here, nxt)
                self._validate(node.get("then"), f"{loc}.then", nxt)
            self._validate(node.get("else"), f"{loc}.else", nxt)
        elif op == "case":
            if isinstance(arg, list):
                self._validate_branches(arg, here, nxt)
                if "when" in node:
                    raise self._err(loc, "a list 'case' takes its branches inline; drop 'when'.")
            else:
                self._validate(arg, here, nxt)
                when = node.get("when")
                if not isinstance(when, Mapping):
                    raise self._err(
                        loc, "'case' needs a list of {when, then} branches or a 'when' object."
                    )
                for k, v in when.items():
                    self._validate(v, f"{loc}.when.{k}", nxt)
            self._validate(node.get("default"), f"{loc}.default", nxt)
        elif op in ("concat", "coalesce"):
            if not isinstance(arg, list):
                raise self._err(here, "needs a list.")
            for i, item in enumerate(arg):
                self._validate(item, f"{here}[{i}]", nxt)
            if not isinstance(node.get("sep", ""), str):
                raise self._err(loc, "'sep' must be a string.")
        elif op == "template":
            if not isinstance(arg, str):
                raise self._err(here, "needs a string.")
            for m in _PLACEHOLDER_RE.finditer(arg):
                if m.group(1) is not None:
                    self._validate_path(m.group(1), here)
        elif op == "path":
            self._validate_path(arg, here)
            self._validate(node.get("default"), f"{loc}.default", nxt)
        elif op == "literal":
            pass
        else:  # upper lower trim number replace substr
            self._validate(arg, here, nxt)
            if op == "number":
                self._validate(node.get("default"), f"{loc}.default", nxt)
            if op == "replace" and (not isinstance(node.get("old"), str) or not node.get("old")):
                raise self._err(loc, "'replace' needs a non-empty 'old' string.")
            if op == "replace" and not isinstance(node.get("new", ""), str):
                raise self._err(loc, "'replace' needs a string 'new'.")
            if op == "substr":
                for k in ("start", "end"):
                    v = node.get(k)
                    if v is not None and (isinstance(v, bool) or not isinstance(v, int)):
                        raise self._err(loc, f"'substr' {k} must be an integer.")

    def _validate_branches(self, branches: List[Any], loc: str, depth: int) -> None:
        if not branches:
            raise self._err(loc, "branch list is empty.")
        for i, br in enumerate(branches):
            if not isinstance(br, Mapping) or set(br) != {"when", "then"}:
                raise self._err(
                    f"{loc}[{i}]", "each branch must be {'when': condition, 'then': value}."
                )
            self._validate_cond(br["when"], f"{loc}[{i}].when", depth + 1)
            self._validate(br["then"], f"{loc}[{i}].then", depth + 1)

    def _validate_cond(self, cond: Any, loc: str, depth: int) -> None:
        if depth > MAX_TEMPLATE_DEPTH:
            raise self._err(loc, f"condition nesting deeper than {MAX_TEMPLATE_DEPTH}.")
        if isinstance(cond, bool):
            return
        if isinstance(cond, str):
            self._validate_path(cond, loc)
            return
        if not isinstance(cond, Mapping):
            raise self._err(loc, "a condition must be an object, a path string, or a boolean.")
        for combo in ("all", "any", "and", "or"):
            if combo in cond:
                if len(cond) != 1 or not isinstance(cond[combo], list):
                    raise self._err(loc, f"'{combo}' needs a list of conditions only.")
                for i, c in enumerate(cond[combo]):
                    self._validate_cond(c, f"{loc}.{combo}[{i}]", depth + 1)
                return
        if "not" in cond:
            if len(cond) != 1:
                raise self._err(loc, "'not' takes a single condition.")
            self._validate_cond(cond["not"], f"{loc}.not", depth + 1)
            return
        if "path" in cond or "expr" in cond:
            unknown = set(cond) - _COND_KEYS
            if unknown:
                raise self._err(loc, f"unknown condition keys: {', '.join(sorted(unknown))}.")
            if "path" in cond:
                self._validate_path(cond["path"], f"{loc}.path")
            else:
                self._validate(cond["expr"], f"{loc}.expr", depth + 1)
            try:
                op = normalize_op(cond.get("op", "eq" if "value" in cond else "not_empty"))
            except BODTransformError as e:
                raise self._err(loc, str(e)) from None
            if op not in _UNARY_OPS and "value" not in cond:
                raise self._err(loc, f"operator '{op}' needs a 'value'.")
            if op in ("in", "not_in") and not isinstance(cond.get("value"), list):
                raise self._err(loc, f"operator '{op}' needs a list 'value'.")
            return
        # compact form {"eq": ["Path", "value"]}
        ops = [k for k in cond if k != "ignore_case"]
        if len(ops) != 1:
            raise self._err(
                loc,
                "expected one operator such as {'eq': ['Path', 'value']}, "
                f"got {sorted(cond)}.",
            )
        raw = ops[0]
        op = _OP_ALIASES.get(raw, raw)
        if op not in _OPS:
            raise self._err(loc, f"unknown operator '{raw}'.")
        args = cond[raw]
        args = args if isinstance(args, list) else [args]
        if not args:
            raise self._err(loc, f"'{raw}' needs at least a path.")
        left = args[0]
        if isinstance(left, Mapping):
            self._validate(left, f"{loc}.{raw}[0]", depth + 1)
        else:
            self._validate_path(left, f"{loc}.{raw}[0]")
        if op in _UNARY_OPS:
            if len(args) > 1:
                raise self._err(loc, f"'{raw}' takes only a path.")
        elif len(args) != 2:
            raise self._err(loc, f"'{raw}' needs [path, value].")
        if not isinstance(cond.get("ignore_case", False), bool):
            raise self._err(loc, "'ignore_case' must be true or false.")

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    def _bind(self, path: str, bindings: Iterable[Optional[str]]) -> Tuple[str, bool]:
        """Replace '*' segments with bindings. Returns (path, has_unbound_star)."""
        sep = self.separator
        it = iter(bindings)
        out: List[str] = []
        unbound = False
        for seg in path.split(sep):
            if seg == "*":
                try:
                    val = next(it)
                except StopIteration:
                    out.append("*")
                    unbound = True
                    continue
                if val is not None:
                    out.append(val)
            else:
                out.append(seg)
        return sep.join(out), unbound

    def _lookup(self, rec: Mapping[str, Any], key: str) -> Tuple[bool, Any]:
        if key in rec:
            return True, rec[key]
        alt = f"{key}{self.separator}#text"
        if alt in rec:
            return True, rec[alt]
        return False, None

    def _lookup_wild(self, rec: Mapping[str, Any], key: str) -> Tuple[bool, Any]:
        """Key with unbound '*': first match (index order, unindexed allowed)."""
        sep = re.escape(self.separator)
        rx = ""
        for i, seg in enumerate(key.split(self.separator)):
            if seg == "*":
                rx += f"(?:{sep}(\\d+))?"
            else:
                rx += (sep if i else "") + re.escape(seg)
        pattern = re.compile(f"^{rx}(?:{sep}#text)?$")
        best: Optional[Tuple[Tuple[int, ...], str]] = None
        for k in rec:
            m = pattern.match(k)
            if m:
                order = tuple(-1 if g is None else int(g) for g in m.groups())
                if best is None or order < best[0]:
                    best = (order, k)
        if best is None:
            return False, None
        return True, rec[best[1]]

    def _resolve(self, raw_path: str, ctx: _Ctx) -> Tuple[bool, Any]:
        path = _clean_path(raw_path)
        sep = self.separator
        first = path.split(sep, 1)[0]
        rec = ctx.record
        if first in ctx.roots or not ctx.frames:
            key, unbound = self._bind(path, (f.binding for f in ctx.frames))
            return self._lookup_wild(rec, key) if unbound else self._lookup(rec, key)
        # relative to the current row, then to outer rows
        for i in range(len(ctx.frames) - 1, -1, -1):
            inner = [f.binding for f in ctx.frames[i + 1:]]
            key, unbound = self._bind(f"{ctx.frames[i].prefix}{sep}{path}", inner)
            found = self._lookup_wild(rec, key) if unbound else self._lookup(rec, key)
            if found[0]:
                return found
        return False, None

    def _value(self, raw_path: str, ctx: _Ctx) -> Any:
        found, val = self._resolve(raw_path, ctx)
        return val if found and val is not None else self.missing

    def _template(self, text: str, ctx: _Ctx) -> str:
        def repl(m: "re.Match[str]") -> str:
            if m.group(0) == "{{":
                return "{"
            if m.group(0) == "}}":
                return "}"
            found, val = self._resolve(m.group(1), ctx)
            return _to_text(val) if found else ""

        return _PLACEHOLDER_RE.sub(repl, text)

    def _rows(self, head: str, rec: Mapping[str, Any]) -> List[_Frame]:
        sep = self.separator
        rx = re.compile(f"^{re.escape(head)}{re.escape(sep)}(\\d+)(?:{re.escape(sep)}|$)")
        idx = sorted({int(m.group(1)) for m in (rx.match(k) for k in rec) if m})
        if idx:
            return [_Frame(f"{head}{sep}{i}", str(i)) for i in idx]
        if any(k == head or k.startswith(head + sep) for k in rec):
            return [_Frame(head, None)]
        return []

    def _repeat(self, node: Mapping[str, Any], ctx: _Ctx) -> List[Any]:
        sep = self.separator
        pattern = _clean_path(node["repeat"])
        head_pattern = pattern[: -len(sep + "*")]
        first = head_pattern.split(sep, 1)[0]
        rows: List[_Frame] = []
        if first in ctx.roots or not ctx.frames:
            head, unbound = self._bind(head_pattern, (f.binding for f in ctx.frames))
            if not unbound:
                rows = self._rows(head, ctx.record)
        else:
            for i in range(len(ctx.frames) - 1, -1, -1):
                inner = [f.binding for f in ctx.frames[i + 1:]]
                head, unbound = self._bind(f"{ctx.frames[i].prefix}{sep}{head_pattern}", inner)
                if not unbound:
                    rows = self._rows(head, ctx.record)
                    if rows:
                        break
        item = node.get("item", {})
        out: List[Any] = []
        for frame in rows:
            row_ctx = ctx.push(frame)
            if "where" in node and not self._cond(node["where"], row_ctx):
                continue
            out.append(self._eval(item, row_ctx))
        return out

    def _eval(self, node: Any, ctx: _Ctx) -> Any:
        if node is None or isinstance(node, (bool, int, float)):
            return node
        if isinstance(node, str):
            if _PLACEHOLDER_RE.search(node):
                return self._template(node, ctx)
            if not node.strip():
                return node
            return self._value(node, ctx)
        if isinstance(node, list):
            return [self._eval(x, ctx) for x in node]
        op = _template_op(node)
        if op is None:
            return {k: self._eval(v, ctx) for k, v in node.items()}
        arg = node[op]
        if op == "repeat":
            return self._repeat(node, ctx)
        if op == "literal":
            return arg
        if op == "template":
            return self._template(arg, ctx)
        if op == "path":
            found, val = self._resolve(arg, ctx)
            if (not found or val is None) and "default" in node:
                return self._arg(node["default"], ctx)
            return val if found and val is not None else self.missing
        if op == "if":
            if isinstance(arg, list):
                for br in arg:
                    if self._cond(br["when"], ctx):
                        return self._arg(br["then"], ctx)
                return self._arg(node.get("else", self.missing), ctx)
            branch = "then" if self._cond(arg, ctx) else "else"
            return self._arg(node.get(branch, self.missing), ctx)
        if op == "case":
            if isinstance(arg, list):
                for br in arg:
                    if self._cond(br["when"], ctx):
                        return self._arg(br["then"], ctx)
                return self._arg(node.get("default", self.missing), ctx)
            subject = _to_text(self._eval(arg, ctx)).strip()
            ic = node.get("ignore_case", False)
            for k, v in node["when"].items():
                if (k.strip().lower() == subject.lower()) if ic else (k.strip() == subject):
                    return self._arg(v, ctx)
            return self._arg(node.get("default", self.missing), ctx)
        if op == "concat":
            parts = [self._arg(x, ctx) for x in arg]
            if node.get("skip_empty", True):
                parts = [p for p in parts if not _is_empty(p)]
            return node.get("sep", "").join(_to_text(p) for p in parts)
        if op == "coalesce":
            for x in arg:
                val = self._arg(x, ctx)
                if not _is_empty(val):
                    return val
            return self.missing
        val = self._eval(arg, ctx)
        if op == "number":
            num = _to_number(val)
            if num is None:
                return self._arg(node.get("default", self.missing), ctx)
            return int(num) if num.is_integer() and abs(num) < 2**53 else num
        if val is None:
            return None
        text = _to_text(val)
        if op == "upper":
            return text.upper()
        if op == "lower":
            return text.lower()
        if op == "trim":
            return text.strip()
        if op == "replace":
            return text.replace(node["old"], node.get("new", ""))
        return text[node.get("start"):node.get("end")]  # substr

    def _arg(self, node: Any, ctx: _Ctx) -> Any:
        """Operator arguments and results (then/else/default/when, concat and
        coalesce items): a plain string is a path when it exists in the record
        or looks like one (contains the separator, '@', '#' or '*'); otherwise
        it is literal text, so ``"then": "high"`` and ``["PO-", "Path"]`` work."""
        if (
            isinstance(node, str)
            and node.strip()
            and not node.startswith("$")
            and not _PLACEHOLDER_RE.search(node)
        ):
            found, val = self._resolve(node, ctx)
            if found:
                return self.missing if val is None else val
            if self.separator in node or any(c in node for c in "@#*"):
                return self.missing
            return node
        return self._eval(node, ctx)

    def _operand(self, node: Any, ctx: _Ctx) -> Any:
        """Right-hand side of a comparison: literal, '$Path', or an expression."""
        if isinstance(node, str):
            if node.startswith("$$"):
                return node[1:]
            if node.startswith("$"):
                return self._resolve(node, ctx)[1]
            return node
        if isinstance(node, Mapping):
            return self._eval(node, ctx)
        return node

    def _cond(self, cond: Any, ctx: _Ctx) -> bool:
        if isinstance(cond, bool):
            return cond
        if isinstance(cond, str):
            return not _is_empty(self._resolve(cond, ctx)[1])
        for combo in ("all", "and"):
            if combo in cond:
                return all(self._cond(c, ctx) for c in cond[combo])
        for combo in ("any", "or"):
            if combo in cond:
                return any(self._cond(c, ctx) for c in cond[combo])
        if "not" in cond:
            return not self._cond(cond["not"], ctx)
        ic = cond.get("ignore_case", False)
        if "path" in cond or "expr" in cond:
            if "path" in cond:
                exists, left = self._resolve(cond["path"], ctx)
            else:
                left = self._eval(cond["expr"], ctx)
                exists = left is not None
            op = normalize_op(cond.get("op", "eq" if "value" in cond else "not_empty"))
            raw_right = cond.get("value")
        else:
            raw = next(k for k in cond if k != "ignore_case")
            op = normalize_op(raw)
            args = cond[raw] if isinstance(cond[raw], list) else [cond[raw]]
            if isinstance(args[0], Mapping):
                left = self._eval(args[0], ctx)
                exists = left is not None
            else:
                exists, left = self._resolve(args[0], ctx)
            raw_right = args[1] if len(args) > 1 else None
        if op in _UNARY_OPS:
            return compare(op, left, exists, None, ic)
        if op in ("in", "not_in"):
            options = raw_right if isinstance(raw_right, list) else [raw_right]
            return compare(op, left, exists, [self._operand(o, ctx) for o in options], ic)
        return compare(op, left, exists, self._operand(raw_right, ctx), ic)


def bod_to_data(
    bod_xml: Union[str, bytes],
    rules: RulesInput,
    verb: Optional[str] = None,
    *,
    single: bool = False,
    include_header: bool = True,
    missing: Any = None,
    kind: str = "auto",
    separator: str = "_",
) -> Any:
    """Map a BOD to your JSON shape and return Python objects.

    Returns a list with one item per noun, or the first item when ``single=True``.
    ``verb=None`` detects the verb. ``rules`` may be a dict, JSON text, or a file path.
    """
    mapper = rules if isinstance(rules, Mapper) else Mapper(
        rules, kind=kind, missing=missing, separator=separator
    )
    return mapper.to_data(bod_xml, verb, single=single, include_header=include_header)


def bod_to_json(
    bod_xml: Union[str, bytes],
    rules: RulesInput,
    verb: Optional[str] = None,
    *,
    single: bool = False,
    include_header: bool = True,
    missing: Any = None,
    kind: str = "auto",
    separator: str = "_",
    indent: Optional[int] = None,
) -> str:
    """Map a BOD to your JSON shape in one call and return a JSON string.

    Example (Infor ION script)::

        from BODtoJSON import bod_to_json
        output_var = bod_to_json(input_var, rules=RULES)
    """
    data = bod_to_data(
        bod_xml,
        rules,
        verb,
        single=single,
        include_header=include_header,
        missing=missing,
        kind=kind,
        separator=separator,
    )
    return json.dumps(data, indent=indent, ensure_ascii=False)
