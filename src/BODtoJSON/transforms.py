"""
Declarative transformation rules for flattened BOD records.

Rules are plain dictionaries (or JSON text) that describe how to derive output
fields from a flattened record. They are evaluated by a small interpreter in
this module: there is no ``eval``/``exec``, no attribute access, no imports and
no regular expressions, so rule files can be stored in Infor ION, shipped in
config repos, or accepted over the optional API without running arbitrary code.

Quick reference (see README "Transformation Rules" for the full grammar)::

    {
      "mode": "merge",                       # or "only"
      "drop": ["PurchaseOrder_*_Note_*"],    # glob patterns removed afterwards
      "rules": {
        "OrderId": "$PurchaseOrder_PurchaseOrderHeader_DocumentID_ID",
        "Label": {"concat": ["PO-", "$PurchaseOrder_PurchaseOrderHeader_DisplayID"]},
        "Status": {"case": "$PurchaseOrder_PurchaseOrderHeader_Status_Code",
                   "when": {"1": "Open", "2": "Closed"}, "default": "Unknown"},
        "Big": {"if": {"path": "PurchaseOrder_PurchaseOrderHeader_ExtendedAmount",
                       "op": "gt", "value": 1000},
                "then": true, "else": false}
      }
    }

Value expressions
    ``"$Path"``            value of a flattened key (``"$$x"`` is the literal ``"$x"``)
    any other scalar       literal
    ``{"path": p, "default": d}``      key lookup with a default
    ``{"literal": v}``     literal (any JSON value, including lists/objects)
    ``{"concat": [e, ...], "sep": "", "skip_empty": true}``
    ``{"template": "PO-{Path}"}``      ``{{``/``}}`` escape braces
    ``{"if": cond, "then": e, "else": e}``
    ``{"if": [{"when": cond, "then": e}, ...], "else": e}``   (else-if chain)
    ``{"case": e, "when": {"A": e, ...} | [{"match": v|[v,...], "then": e}],
       "default": e, "ignore_case": false}``
    ``{"coalesce": [e, ...]}``         first non-empty value
    ``{"upper": e}``, ``{"lower": e}``, ``{"trim": e}``
    ``{"replace": e, "old": "a", "new": "b"}``
    ``{"substr": e, "start": 0, "end": 3}``
    ``{"number": e, "default": d}``    int/float conversion

Conditions
    ``{"path": p, "op": "eq", "value": v}`` (or ``"expr": e`` instead of path).
    ``value`` is itself an expression, so ``"$OtherPath"`` compares two fields.
    ops: eq ne gt ge lt le (also == != > >= < <=), in not_in, contains
    not_contains, starts_with ends_with, exists missing, empty not_empty.
    ``{"all": [c, ...]}``, ``{"any": [c, ...]}``, ``{"not": c}``, ``"$Path"``
    (true when the value is not empty), ``true`` / ``false``.

Repeated elements
    A ``*`` path segment binds to the index of repeated siblings
    (``PurchaseOrder_Line_*_Qty`` matches ``PurchaseOrder_Line_0_Qty``,
    ``PurchaseOrder_Line_1_Qty`` and, for a single line, ``PurchaseOrder_Line_Qty``).
    When the target contains ``*`` the rule runs once per index found.
"""

import json
import re
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple, Union

__all__ = [
    "BODTransformError",
    "TransformRules",
    "apply_rules",
    "compile_rules",
]


class BODTransformError(ValueError):
    """Raised for an invalid rule definition or a rule that cannot be applied."""


RulesLike = Union["TransformRules", Mapping[str, Any], str, bytes]

MAX_RULE_DEPTH = 64
MAX_RULES = 10_000

_EXPR_KEYS = {
    "path": {"default"},
    "literal": set(),
    "concat": {"sep", "skip_empty"},
    "template": set(),
    "if": {"then", "else"},
    "case": {"when", "default", "ignore_case"},
    "coalesce": set(),
    "upper": set(),
    "lower": set(),
    "trim": set(),
    "replace": {"old", "new"},
    "substr": {"start", "end"},
    "number": {"default"},
}

_OP_ALIASES = {
    "==": "eq",
    "!=": "ne",
    ">": "gt",
    ">=": "ge",
    "<": "lt",
    "<=": "le",
    "gte": "ge",
    "lte": "le",
    "not_exists": "missing",
    "startswith": "starts_with",
    "endswith": "ends_with",
}
_OPS = {
    "eq", "ne", "gt", "ge", "lt", "le", "in", "not_in", "contains",
    "not_contains", "starts_with", "ends_with", "exists", "missing",
    "empty", "not_empty",
}
_UNARY_OPS = {"exists", "missing", "empty", "not_empty"}
_COND_KEYS = {"path", "expr", "op", "value", "ignore_case"}

_NON_EXPR_KEYS = {
    "match", "sep", "old", "new", "start", "end", "op", "ignore_case", "skip_empty",
}

_TEMPLATE_RE = re.compile(r"\{\{|\}\}|\{([^{}]+)\}")

Binding = Tuple[Optional[str], ...]


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _to_number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return None


class _Rule:
    __slots__ = ("target", "expr", "stars", "starred_paths")

    def __init__(self, target: str, expr: Any, stars: int, starred_paths: List[str]):
        self.target = target
        self.expr = expr
        self.stars = stars
        self.starred_paths = starred_paths


class TransformRules:
    """A validated, reusable set of transformation rules.

    Args:
        config: either a mapping of ``output_field -> expression`` or a mapping
            with a ``"rules"`` key plus optional ``"mode"`` (``"merge"`` keeps
            all source fields and adds/overrides rule outputs; ``"only"`` emits
            rule outputs only) and ``"drop"`` (list of glob patterns removed
            from the output). JSON text is accepted too.
        separator: the flattening separator used in paths (default ``"_"``).
        default_mode: the mode used when the config does not set one.

    Rules run in order and see earlier outputs, so a later rule may reference
    a field created by an earlier rule.
    """

    def __init__(
        self,
        config: Union[Mapping[str, Any], str, bytes],
        separator: str = "_",
        default_mode: str = "merge",
    ):
        if isinstance(config, (str, bytes, bytearray)):
            try:
                config = json.loads(config)
            except (ValueError, RecursionError) as e:
                raise BODTransformError(f"Rules are not valid JSON: {e}") from e
        if not isinstance(config, Mapping):
            raise BODTransformError("Rules must be a JSON object / dict.")
        if not separator:
            raise BODTransformError("Separator must be a non-empty string.")
        self.separator = separator

        if "rules" in config and isinstance(config["rules"], Mapping):
            extra = set(config) - {"rules", "mode", "drop", "description", "version"}
            if extra:
                raise BODTransformError(
                    f"Unknown top-level rule keys: {', '.join(sorted(extra))}."
                )
            rules = config["rules"]
            mode = config.get("mode", default_mode)
            drop = config.get("drop", [])
        else:
            rules = config
            mode = default_mode
            drop = []

        if mode not in ("merge", "only"):
            raise BODTransformError("mode must be 'merge' or 'only'.")
        if not isinstance(drop, list) or not all(isinstance(d, str) for d in drop):
            raise BODTransformError("drop must be a list of strings.")
        if len(rules) > MAX_RULES:
            raise BODTransformError(f"Too many rules (max {MAX_RULES}).")

        self.mode = mode
        self.drop = list(drop)
        self._drop_res = [self._glob_to_re(d) for d in drop]
        self._rules: List[_Rule] = []
        for target, expr in rules.items():
            if not isinstance(target, str) or not target:
                raise BODTransformError("Rule targets must be non-empty strings.")
            try:
                self._validate_expr(expr, 0)
            except BODTransformError as e:
                raise BODTransformError(f"Rule '{target}': {e}") from None
            stars = self._count_stars(target)
            starred = [p for p in self._collect_paths(expr) if self._count_stars(p)]
            for p in starred:
                if self._count_stars(p) != stars:
                    raise BODTransformError(
                        f"Rule '{target}': path '{p}' has {self._count_stars(p)} '*' "
                        f"segment(s) but the target has {stars}."
                    )
            if stars and not starred:
                raise BODTransformError(
                    f"Rule '{target}': a '*' target needs at least one '*' path."
                )
            self._rules.append(_Rule(target, expr, stars, starred))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def targets(self) -> List[str]:
        return [r.target for r in self._rules]

    def apply(self, record: Mapping[str, Any]) -> Dict[str, Any]:
        """Apply the rules to one flattened record and return a new dict."""
        if not isinstance(record, Mapping):
            raise BODTransformError("Each record must be a JSON object / dict.")
        out: Dict[str, Any] = dict(record) if self.mode == "merge" else {}
        source = dict(record)

        def lookup(key: str) -> Tuple[bool, Any]:
            if key in out:
                return True, out[key]
            if key in source:
                return True, source[key]
            return False, None

        def all_keys() -> Iterable[str]:
            seen = set(out)
            yield from out
            for k in source:
                if k not in seen:
                    yield k

        for rule in self._rules:
            if not rule.stars:
                out[rule.target] = self._eval(rule.expr, lookup, ())
                continue
            for binding in self._bindings(rule, all_keys()):
                target = self._bind(rule.target, binding)
                out[target] = self._eval(rule.expr, lookup, binding)

        if self._drop_res:
            protected = set(self.targets)
            out = {
                k: v
                for k, v in out.items()
                if k in protected or not any(r.match(k) for r in self._drop_res)
            }
        return out

    def apply_many(self, records: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        return [self.apply(r) for r in records]

    __call__ = apply

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @staticmethod
    def _glob_to_re(pattern: str) -> "re.Pattern[str]":
        return re.compile("^" + ".*".join(re.escape(p) for p in pattern.split("*")) + "$")

    def _count_stars(self, path: str) -> int:
        return sum(1 for seg in path.split(self.separator) if seg == "*")

    def _validate_path(self, path: Any) -> None:
        if not isinstance(path, str) or not path:
            raise BODTransformError("A path must be a non-empty string.")
        segs = path.split(self.separator)
        if segs[0] == "*":
            raise BODTransformError(f"Path '{path}' cannot start with '*'.")
        for seg in segs:
            if "*" in seg and seg != "*":
                raise BODTransformError(
                    f"Path '{path}': '*' must be a whole segment (e.g. Line{self.separator}*)."
                )

    def _validate_expr(self, expr: Any, depth: int) -> None:
        if depth > MAX_RULE_DEPTH:
            raise BODTransformError(f"Rule nesting deeper than {MAX_RULE_DEPTH}.")
        if expr is None or isinstance(expr, (bool, int, float)):
            return
        if isinstance(expr, str):
            if expr.startswith("$") and not expr.startswith("$$"):
                self._validate_path(expr[1:])
            return
        if isinstance(expr, list):
            raise BODTransformError(
                "Lists are not expressions; wrap literal lists as {'literal': [...]}."
            )
        if not isinstance(expr, Mapping):
            raise BODTransformError(f"Unsupported expression type {type(expr).__name__}.")

        ops = [k for k in expr if k in _EXPR_KEYS]
        if len(ops) != 1:
            raise BODTransformError(
                "An expression object needs exactly one operator key out of: "
                + ", ".join(sorted(_EXPR_KEYS))
                + f" (got {sorted(expr)})."
            )
        op = ops[0]
        unknown = set(expr) - {op} - _EXPR_KEYS[op]
        if unknown:
            raise BODTransformError(f"'{op}' does not accept: {', '.join(sorted(unknown))}.")
        arg = expr[op]
        nxt = depth + 1

        if op == "path":
            self._validate_path(arg[1:] if isinstance(arg, str) and arg.startswith("$") else arg)
            self._validate_expr(expr.get("default"), nxt)
        elif op == "literal":
            pass
        elif op in ("concat", "coalesce"):
            if not isinstance(arg, list):
                raise BODTransformError(f"'{op}' needs a list.")
            for item in arg:
                self._validate_expr(item, nxt)
            if op == "concat":
                if not isinstance(expr.get("sep", ""), str):
                    raise BODTransformError("'sep' must be a string.")
                if not isinstance(expr.get("skip_empty", True), bool):
                    raise BODTransformError("'skip_empty' must be true or false.")
        elif op == "template":
            if not isinstance(arg, str):
                raise BODTransformError("'template' needs a string.")
            for m in _TEMPLATE_RE.finditer(arg):
                if m.group(1) is not None:
                    self._validate_path(m.group(1).strip())
        elif op == "if":
            if isinstance(arg, list):
                if not arg:
                    raise BODTransformError("'if' branch list is empty.")
                for br in arg:
                    if not isinstance(br, Mapping) or set(br) != {"when", "then"}:
                        raise BODTransformError(
                            "Each 'if' branch must be {'when': condition, 'then': value}."
                        )
                    self._validate_cond(br["when"], nxt)
                    self._validate_expr(br["then"], nxt)
                if "then" in expr:
                    raise BODTransformError("Use 'then' inside each branch of a list 'if'.")
            else:
                self._validate_cond(arg, nxt)
                self._validate_expr(expr.get("then"), nxt)
            self._validate_expr(expr.get("else"), nxt)
        elif op == "case":
            self._validate_expr(arg, nxt)
            when = expr.get("when")
            if isinstance(when, Mapping):
                for v in when.values():
                    self._validate_expr(v, nxt)
            elif isinstance(when, list):
                for br in when:
                    if not isinstance(br, Mapping) or set(br) != {"match", "then"}:
                        raise BODTransformError(
                            "Each 'case' branch must be {'match': value(s), 'then': value}."
                        )
                    self._validate_expr(br["then"], nxt)
            else:
                raise BODTransformError("'case' needs a 'when' object or list.")
            self._validate_expr(expr.get("default"), nxt)
            if not isinstance(expr.get("ignore_case", False), bool):
                raise BODTransformError("'ignore_case' must be true or false.")
        elif op in ("upper", "lower", "trim"):
            self._validate_expr(arg, nxt)
        elif op == "replace":
            self._validate_expr(arg, nxt)
            if not isinstance(expr.get("old"), str) or not expr.get("old"):
                raise BODTransformError("'replace' needs a non-empty 'old' string.")
            if not isinstance(expr.get("new", ""), str):
                raise BODTransformError("'replace' needs a string 'new'.")
        elif op == "substr":
            self._validate_expr(arg, nxt)
            for k in ("start", "end"):
                v = expr.get(k)
                if v is not None and (isinstance(v, bool) or not isinstance(v, int)):
                    raise BODTransformError(f"'substr' {k} must be an integer.")
        elif op == "number":
            self._validate_expr(arg, nxt)
            self._validate_expr(expr.get("default"), nxt)

    def _validate_cond(self, cond: Any, depth: int) -> None:
        if depth > MAX_RULE_DEPTH:
            raise BODTransformError(f"Rule nesting deeper than {MAX_RULE_DEPTH}.")
        if isinstance(cond, bool):
            return
        if isinstance(cond, str):
            if not cond.startswith("$") or cond.startswith("$$"):
                raise BODTransformError(
                    f"A string condition must be a '$path' reference (got {cond!r})."
                )
            self._validate_path(cond[1:])
            return
        if not isinstance(cond, Mapping):
            raise BODTransformError("A condition must be an object, '$path', or boolean.")
        for combo in ("all", "any", "and", "or"):
            if combo in cond:
                if len(cond) != 1 or not isinstance(cond[combo], list):
                    raise BODTransformError(f"'{combo}' needs a list of conditions only.")
                for c in cond[combo]:
                    self._validate_cond(c, depth + 1)
                return
        if "not" in cond:
            if len(cond) != 1:
                raise BODTransformError("'not' takes a single condition.")
            self._validate_cond(cond["not"], depth + 1)
            return
        unknown = set(cond) - _COND_KEYS
        if unknown:
            raise BODTransformError(f"Unknown condition keys: {', '.join(sorted(unknown))}.")
        if ("path" in cond) == ("expr" in cond):
            raise BODTransformError("A condition needs exactly one of 'path' or 'expr'.")
        if "path" in cond:
            p = cond["path"]
            self._validate_path(p[1:] if isinstance(p, str) and p.startswith("$") else p)
        else:
            self._validate_expr(cond["expr"], depth + 1)
        op = self._norm_op(cond)
        if op not in _UNARY_OPS and "value" not in cond:
            raise BODTransformError(f"Operator '{op}' needs a 'value'.")
        value = cond.get("value")
        if op in ("in", "not_in"):
            if not isinstance(value, list):
                raise BODTransformError(f"Operator '{op}' needs a list 'value'.")
            for v in value:
                self._validate_expr(v, depth + 1)
        elif "value" in cond:
            self._validate_expr(value, depth + 1)
        if not isinstance(cond.get("ignore_case", False), bool):
            raise BODTransformError("'ignore_case' must be true or false.")

    @staticmethod
    def _norm_op(cond: Mapping[str, Any]) -> str:
        return normalize_op(cond.get("op", "eq" if "value" in cond else "not_empty"))

    def _collect_paths(self, expr: Any) -> List[str]:
        found: List[str] = []

        def walk(node: Any, is_cond: bool = False) -> None:
            if isinstance(node, str):
                if node.startswith("$") and not node.startswith("$$"):
                    found.append(node[1:])
            elif isinstance(node, list):
                for n in node:
                    walk(n, is_cond)
            elif isinstance(node, Mapping):
                for k, v in node.items():
                    if k == "literal":
                        continue
                    if k == "path" and isinstance(v, str):
                        found.append(v[1:] if v.startswith("$") else v)
                    elif k == "template" and isinstance(v, str):
                        found.extend(
                            m.group(1).strip()
                            for m in _TEMPLATE_RE.finditer(v)
                            if m.group(1) is not None
                        )
                    elif k in _NON_EXPR_KEYS:
                        continue
                    else:
                        walk(v)

        walk(expr)
        return found

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    def _star_regex(self, path: str) -> "re.Pattern[str]":
        sep = re.escape(self.separator)
        out = ""
        for i, seg in enumerate(path.split(self.separator)):
            if seg == "*":
                out += f"(?:{sep}(\\d+))?"
            else:
                out += (sep if i else "") + re.escape(seg)
        # Allow the attribute/text suffix shortcut: Path -> Path_#text
        return re.compile(f"^{out}(?:{sep}#text)?$")

    def _bindings(self, rule: _Rule, keys: Iterable[str]) -> List[Binding]:
        regexes = [self._star_regex(p) for p in rule.starred_paths]
        found: Dict[Binding, None] = {}
        for key in keys:
            for rx in regexes:
                m = rx.match(key)
                if m:
                    found[tuple(m.groups())] = None

        def sort_key(b: Binding) -> Tuple[int, ...]:
            return tuple(-1 if g is None else int(g) for g in b)

        return sorted(found, key=sort_key)

    def _bind(self, path: str, binding: Binding) -> str:
        if not binding:
            return path
        segs = path.split(self.separator)
        out: List[str] = []
        it = iter(binding)
        for seg in segs:
            if seg == "*":
                val = next(it, None)
                if val is not None:
                    out.append(val)
            else:
                out.append(seg)
        return self.separator.join(out)

    def _resolve(
        self,
        path: str,
        lookup: Callable[[str], Tuple[bool, Any]],
        binding: Binding,
    ) -> Tuple[bool, Any]:
        key = self._bind(path, binding) if binding else path
        ok, val = lookup(key)
        if not ok:
            ok, val = lookup(f"{key}{self.separator}#text")
        return ok, val

    def _eval(self, expr: Any, lookup: Callable[[str], Tuple[bool, Any]], b: Binding) -> Any:
        if expr is None or isinstance(expr, (bool, int, float)):
            return expr
        if isinstance(expr, str):
            if expr.startswith("$$"):
                return expr[1:]
            if expr.startswith("$"):
                return self._resolve(expr[1:], lookup, b)[1]
            return expr
        op = next(k for k in expr if k in _EXPR_KEYS)
        arg = expr[op]

        if op == "path":
            p = arg[1:] if arg.startswith("$") else arg
            ok, val = self._resolve(p, lookup, b)
            if (not ok or val is None) and "default" in expr:
                return self._eval(expr["default"], lookup, b)
            return val
        if op == "literal":
            return arg
        if op == "concat":
            parts = [self._eval(e, lookup, b) for e in arg]
            if expr.get("skip_empty", True):
                parts = [p for p in parts if not _is_empty(p)]
            return expr.get("sep", "").join(_to_text(p) for p in parts)
        if op == "template":

            def repl(m: "re.Match[str]") -> str:
                if m.group(0) == "{{":
                    return "{"
                if m.group(0) == "}}":
                    return "}"
                return _to_text(self._resolve(m.group(1).strip(), lookup, b)[1])

            return _TEMPLATE_RE.sub(repl, arg)
        if op == "if":
            if isinstance(arg, list):
                for br in arg:
                    if self._cond(br["when"], lookup, b):
                        return self._eval(br["then"], lookup, b)
                return self._eval(expr.get("else"), lookup, b)
            branch = "then" if self._cond(arg, lookup, b) else "else"
            return self._eval(expr.get(branch), lookup, b)
        if op == "case":
            subject = self._eval(arg, lookup, b)
            ic = expr.get("ignore_case", False)
            key = _to_text(subject).strip()
            if ic:
                key = key.lower()
            when = expr["when"]
            if isinstance(when, Mapping):
                for k, v in when.items():
                    if (k.strip().lower() if ic else k.strip()) == key:
                        return self._eval(v, lookup, b)
            else:
                for br in when:
                    matches = br["match"] if isinstance(br["match"], list) else [br["match"]]
                    for mv in matches:
                        cand = _to_text(mv).strip()
                        if (cand.lower() if ic else cand) == key:
                            return self._eval(br["then"], lookup, b)
            return self._eval(expr.get("default"), lookup, b)
        if op == "coalesce":
            for e in arg:
                val = self._eval(e, lookup, b)
                if not _is_empty(val):
                    return val
            return None
        if op in ("upper", "lower", "trim"):
            val = self._eval(arg, lookup, b)
            if val is None:
                return None
            text = _to_text(val)
            if op == "upper":
                return text.upper()
            return text.lower() if op == "lower" else text.strip()
        if op == "replace":
            val = self._eval(arg, lookup, b)
            if val is None:
                return None
            return _to_text(val).replace(expr["old"], expr.get("new", ""))
        if op == "substr":
            val = self._eval(arg, lookup, b)
            if val is None:
                return None
            return _to_text(val)[expr.get("start"):expr.get("end")]
        # op == "number"
        val = self._eval(arg, lookup, b)
        num = _to_number(val)
        if num is None:
            return self._eval(expr.get("default"), lookup, b)
        return int(num) if num.is_integer() and abs(num) < 2**53 else num

    def _cond(self, cond: Any, lookup: Callable[[str], Tuple[bool, Any]], b: Binding) -> bool:
        if isinstance(cond, bool):
            return cond
        if isinstance(cond, str):
            return not _is_empty(self._resolve(cond[1:], lookup, b)[1])
        for combo in ("all", "and"):
            if combo in cond:
                return all(self._cond(c, lookup, b) for c in cond[combo])
        for combo in ("any", "or"):
            if combo in cond:
                return any(self._cond(c, lookup, b) for c in cond[combo])
        if "not" in cond:
            return not self._cond(cond["not"], lookup, b)

        if "path" in cond:
            p = cond["path"]
            exists, left = self._resolve(p[1:] if p.startswith("$") else p, lookup, b)
        else:
            left = self._eval(cond["expr"], lookup, b)
            exists = left is not None
        op = self._norm_op(cond)
        ic = cond.get("ignore_case", False)
        if op in _UNARY_OPS:
            return compare(op, left, exists, None, ic)
        raw_value = cond["value"]
        if op in ("in", "not_in"):
            right: Any = [self._eval(v, lookup, b) for v in raw_value]
        else:
            right = self._eval(raw_value, lookup, b)
        return compare(op, left, exists, right, ic)



def _equals(left: Any, right: Any, ignore_case: bool) -> bool:
    if isinstance(right, bool) or isinstance(left, bool):
        return _to_text(left).strip().lower() == _to_text(right).strip().lower()
    if isinstance(right, (int, float)) or isinstance(left, (int, float)):
        ln, rn = _to_number(left), _to_number(right)
        if ln is not None and rn is not None:
            return ln == rn
    lt, rt = _to_text(left), _to_text(right)
    if ignore_case:
        return lt.lower() == rt.lower()
    return lt == rt


def normalize_op(raw: Any) -> str:
    """Return the canonical operator name, or raise BODTransformError."""
    if not isinstance(raw, str):
        raise BODTransformError("'op' must be a string.")
    op = _OP_ALIASES.get(raw, raw)
    if op not in _OPS:
        raise BODTransformError(f"Unknown operator '{raw}'.")
    return op


def compare(op: str, left: Any, exists: bool, right: Any, ignore_case: bool = False) -> bool:
    """Evaluate one comparison. ``right`` is a list for ``in`` / ``not_in``."""
    if op == "exists":
        return exists
    if op == "missing":
        return not exists
    if op == "empty":
        return _is_empty(left)
    if op == "not_empty":
        return not _is_empty(left)
    if op in ("in", "not_in"):
        hit = any(_equals(left, o, ignore_case) for o in right)
        return hit if op == "in" else not hit
    if op == "eq":
        return _equals(left, right, ignore_case)
    if op == "ne":
        return not _equals(left, right, ignore_case)

    lt, rt = _to_text(left), _to_text(right)
    if ignore_case:
        lt, rt = lt.lower(), rt.lower()
    if op == "contains":
        return rt in lt
    if op == "not_contains":
        return rt not in lt
    if op == "starts_with":
        return lt.startswith(rt)
    if op == "ends_with":
        return lt.endswith(rt)

    # Ordering: numeric when both sides are numbers, else text.
    ln, rn = _to_number(left), _to_number(right)
    if ln is not None and rn is not None:
        a: Any = ln
        c: Any = rn
    elif left is None or right is None:
        return False
    else:
        a, c = lt, rt
    if op == "gt":
        return bool(a > c)
    if op == "ge":
        return bool(a >= c)
    if op == "lt":
        return bool(a < c)
    return bool(a <= c)  # le


def compile_rules(
    rules: RulesLike, separator: str = "_", default_mode: str = "merge"
) -> TransformRules:
    """Return a :class:`TransformRules` from a dict, JSON text, or an existing instance."""
    if isinstance(rules, TransformRules):
        return rules
    return TransformRules(rules, separator=separator, default_mode=default_mode)


def apply_rules(
    records: Union[Mapping[str, Any], Iterable[Mapping[str, Any]]],
    rules: RulesLike,
    separator: str = "_",
) -> Any:
    """Apply rules to one flattened record (dict) or a list of records."""
    compiled = compile_rules(rules, separator=separator)
    if isinstance(records, Mapping):
        return compiled.apply(records)
    return compiled.apply_many(records)
