import json
import warnings
from typing import Any, Dict, List, Optional, Union
from xml.etree.ElementTree import ParseError

from .safe_xml import SafeXMLError, parse_xml
from .transforms import RulesLike, TransformRules, compile_rules


class BODParseError(Exception):
    """Raised for malformed XML, entity/DTD rejection, oversize, or over-deep documents."""


class BODStructureError(ValueError):
    """Raised for missing DataArea, verb, or noun elements."""


class BODConverter:
    """Safe, namespace-aware OAGIS BOD to flattened JSON converter."""

    DEFAULT_MAX_SIZE = 10 * 1024 * 1024  # 10 MiB
    DEFAULT_MAX_DEPTH = 256

    def __init__(
        self,
        pnode: str = "DataArea",
        separator: str = "_",
        max_size: Optional[int] = None,
        max_depth: Optional[int] = None,
    ):
        self.pnode = pnode
        self.separator = separator
        self.max_size = max_size if max_size is not None else self.DEFAULT_MAX_SIZE
        self.max_depth = max_depth if max_depth is not None else self.DEFAULT_MAX_DEPTH

    @staticmethod
    def _input_size(bod_xml: Union[str, bytes]) -> int:
        if isinstance(bod_xml, (bytes, bytearray, memoryview)):
            return len(bod_xml)
        return len(bod_xml.encode("utf-8"))

    def _check_size(self, bod_xml: Union[str, bytes]) -> None:
        if self._input_size(bod_xml) > self.max_size:
            raise BODParseError(
                f"Document exceeds maximum allowed size of {self.max_size} bytes."
            )

    def _parse(self, bod_xml: Union[str, bytes]):
        """Parse XML with the stdlib-only hardened parser and return the root."""
        self._check_size(bod_xml)
        try:
            return parse_xml(
                bod_xml, max_size=self.max_size, max_depth=self.max_depth
            )
        except SafeXMLError as e:
            raise BODParseError(str(e)) from e
        except ParseError as e:
            raise BODParseError(f"Failed to parse XML: {e}") from e

    def _rules(self, rules: Optional[RulesLike]) -> Optional[TransformRules]:
        """Compile rules (dict / JSON text / TransformRules) with this separator."""
        if rules is None:
            return None
        return compile_rules(rules, separator=self.separator)

    @staticmethod
    def _local_name(tag: str) -> str:
        """Return the local part of an ElementTree tag, ignoring namespaces."""
        return tag.split("}", 1)[-1] if "}" in tag else tag

    def _find_direct_local(self, elem, local_name: str):
        """Find the first direct child with the given local name."""
        if elem is None:
            return None
        for child in list(elem):
            if self._local_name(child.tag) == local_name:
                return child
        # The element itself (e.g. a document whose root is DataArea)
        if self._local_name(elem.tag) == local_name:
            return elem
        return None

    def _find_local(self, elem, local_name: str):
        """Find the first element with the given local name (descendants allowed).

        Used for ApplicationArea, which is a sibling of DataArea under the root.
        Verb and DataArea lookups use _find_direct_local instead.
        """
        if elem is None:
            return None
        if self._local_name(elem.tag) == local_name:
            return elem
        found = elem.find(f".//{{*}}{local_name}")
        if found is not None:
            return found
        for descendant in elem.iter():
            if self._local_name(descendant.tag) == local_name:
                return descendant
        return None

    def _remove_direct_child(self, parent, child, verb: str) -> None:
        try:
            parent.remove(child)
        except ValueError as e:
            raise BODStructureError(
                f"Verb '{verb}' is not a direct child of '{self.pnode}'."
            ) from e

    def _prepare_noun_element(self, bod_xml: Union[str, bytes], verb: str):
        """Extract the first noun under DataArea after removing the verb."""
        root = self._parse(bod_xml)
        data_area = self._find_direct_local(root, self.pnode)
        if data_area is None:
            raise BODStructureError(f"Target node '{self.pnode}' not found.")

        verb_node = self._find_direct_local(data_area, verb)
        if verb_node is None:
            raise BODStructureError(f"Verb '{verb}' not found under '{self.pnode}'.")

        self._remove_direct_child(data_area, verb_node, verb)

        children = list(data_area)
        if not children:
            raise BODStructureError(f"No Noun element found inside '{self.pnode}'.")

        return children[0]

    def _strip_ns(self, tag: str) -> str:
        """Strips any residual {namespace} URI prefixes from ElementTree tags."""
        return self._local_name(tag)

    def _flatten_element(self, elem, prefix: str = "") -> Dict[str, Any]:
        """Recursively flatten an element into a dictionary using local names."""
        flat_dict: Dict[str, Any] = {}
        tag_name = self._strip_ns(elem.tag)
        current_prefix = f"{prefix}{self.separator}{tag_name}" if prefix else tag_name

        for attr_k, attr_v in elem.attrib.items():
            clean_attr = self._strip_ns(attr_k)
            flat_dict[f"{current_prefix}{self.separator}@{clean_attr}"] = attr_v

        children = list(elem)
        text_val = elem.text.strip() if elem.text and elem.text.strip() else None

        if not children:
            if elem.attrib:
                if text_val is not None:
                    flat_dict[f"{current_prefix}{self.separator}#text"] = text_val
            else:
                flat_dict[current_prefix] = text_val
            return flat_dict

        if text_val is not None:
            flat_dict[f"{current_prefix}{self.separator}#text"] = text_val

        grouped_children: Dict[str, List] = {}
        for child in children:
            c_tag = self._strip_ns(child.tag)
            grouped_children.setdefault(c_tag, []).append(child)

        for c_tag, c_list in grouped_children.items():
            if len(c_list) == 1:
                flat_dict.update(self._flatten_element(c_list[0], current_prefix))
            else:
                for idx, child_elem in enumerate(c_list):
                    indexed_prefix = f"{current_prefix}{self.separator}{c_tag}{self.separator}{idx}"
                    flat_dict.update(self._flatten_indexed_child(child_elem, indexed_prefix))

        return flat_dict

    def _flatten_indexed_child(self, elem, indexed_prefix: str) -> Dict[str, Any]:
        """Flatten a repeating sibling without duplicating the tag name in the key."""
        flat_dict: Dict[str, Any] = {}

        for attr_k, attr_v in elem.attrib.items():
            clean_attr = self._strip_ns(attr_k)
            flat_dict[f"{indexed_prefix}{self.separator}@{clean_attr}"] = attr_v

        children = list(elem)
        text_val = elem.text.strip() if elem.text and elem.text.strip() else None

        if not children:
            if elem.attrib:
                if text_val is not None:
                    flat_dict[f"{indexed_prefix}{self.separator}#text"] = text_val
            else:
                flat_dict[indexed_prefix] = text_val
            return flat_dict

        if text_val is not None:
            flat_dict[f"{indexed_prefix}{self.separator}#text"] = text_val

        grouped_children: Dict[str, List] = {}
        for child in children:
            c_tag = self._strip_ns(child.tag)
            grouped_children.setdefault(c_tag, []).append(child)

        for c_tag, c_list in grouped_children.items():
            if len(c_list) == 1:
                flat_dict.update(self._flatten_element(c_list[0], indexed_prefix))
            else:
                for idx, child_elem in enumerate(c_list):
                    sub_prefix = f"{indexed_prefix}{self.separator}{c_tag}{self.separator}{idx}"
                    flat_dict.update(self._flatten_indexed_child(child_elem, sub_prefix))

        return flat_dict

    def _extract_header_context(self, root, verb_node) -> Dict[str, Any]:
        """Captures ApplicationArea and Verb metadata."""
        context: Dict[str, Any] = {}
        app_area = self._find_local(root, "ApplicationArea")
        if app_area is not None:
            context.update(self._flatten_element(app_area))
        if verb_node is not None:
            context.update(self._flatten_element(verb_node))
        return context

    def to_records(
        self,
        bod_xml: Union[str, bytes],
        verb: str,
        include_header: bool = False,
        rules: Optional[RulesLike] = None,
    ) -> List[Dict[str, Any]]:
        """
        Parses OAGIS XML into a list of flattened dictionaries (one per noun).

        ``rules`` (dict, JSON text, or TransformRules) are applied to each
        record after flattening (and after header merge when include_header).
        Raises BODParseError, BODStructureError, or BODTransformError on failure.
        """
        compiled = self._rules(rules)
        root = self._parse(bod_xml)
        data_area = self._find_direct_local(root, self.pnode)
        if data_area is None:
            raise BODStructureError(f"Target node '{self.pnode}' not found.")

        verb_node = self._find_direct_local(data_area, verb)
        if verb_node is None:
            raise BODStructureError(f"Verb '{verb}' not found under '{self.pnode}'.")

        header_context = (
            self._extract_header_context(root, verb_node) if include_header else {}
        )

        self._remove_direct_child(data_area, verb_node, verb)

        noun_nodes = list(data_area)
        if not noun_nodes:
            raise BODStructureError(f"No Noun element found inside '{self.pnode}'.")

        records: List[Dict[str, Any]] = []
        for noun_elem in noun_nodes:
            flat_record = self._flatten_element(noun_elem)
            if header_context:
                records.append({**header_context, **flat_record})
            else:
                records.append(flat_record)

        if compiled is not None:
            records = compiled.apply_many(records)
        return records

    def project(
        self,
        bod_xml: Union[str, bytes],
        verb: str,
        schema: Dict[str, Any],
        include_header: bool = True,
        coerce_booleans: bool = True,
        rules: Optional[RulesLike] = None,
    ) -> List[Dict[str, Any]]:
        """Projects flattened records into a target schema.

        Optional ``rules`` run first, so the schema can reference rule outputs.
        """
        records = self.to_records(
            bod_xml, verb, include_header=include_header, rules=rules
        )
        projected_items: List[Dict[str, Any]] = []

        class _SafeDict(dict):
            def __missing__(self, key):
                return ""

        for rec in records:
            clean_rec = _SafeDict(
                {k: ("" if v is None else str(v).strip()) for k, v in rec.items()}
            )
            item: Dict[str, Any] = {}

            for target_field, rule in schema.items():
                if callable(rule):
                    val = rule(rec)
                elif isinstance(rule, str):
                    if "{" in rule and "}" in rule:
                        val = rule.format_map(clean_rec)
                    elif rule in rec:
                        val = rec[rule]
                    else:
                        val = rule
                else:
                    val = rule

                if coerce_booleans and isinstance(val, str):
                    low = val.lower()
                    if low == "true":
                        val = True
                    elif low == "false":
                        val = False

                item[target_field] = val

            projected_items.append(item)

        return projected_items

    def to_json(
        self,
        bod_xml: Union[str, bytes],
        verb: str,
        raise_on_error: bool = False,
        rules: Optional[RulesLike] = None,
    ) -> str:
        """
        Converts OAGIS XML to a single flat JSON string (first noun only).

        By default returns an error JSON object on failure (backward compatible).
        Set raise_on_error=True to raise BODParseError / BODStructureError instead.
        Invalid ``rules`` always raise BODTransformError (a configuration error).
        """
        compiled = self._rules(rules)
        try:
            noun_elem = self._prepare_noun_element(bod_xml, verb)
            flattened = self._flatten_element(noun_elem)
            if compiled is not None:
                flattened = compiled.apply(flattened)
            return json.dumps(flattened)
        except (BODParseError, BODStructureError) as e:
            if raise_on_error:
                raise
            return json.dumps({"status": "error", "message": str(e)})

    def to_ndjson(
        self,
        bod_xml: Union[str, bytes],
        verb: str,
        raise_on_error: bool = False,
        rules: Optional[RulesLike] = None,
        include_header: bool = False,
    ) -> str:
        """
        Converts OAGIS XML into NDJSON (one record per noun).

        Default returns error JSON on failure. raise_on_error=True raises.
        ``include_header`` adds ApplicationArea/verb fields to every line.
        """
        compiled = self._rules(rules)
        try:
            records = self.to_records(
                bod_xml, verb, include_header=include_header, rules=compiled
            )
            lines = [
                json.dumps(rec, separators=(",", ":")).strip() for rec in records
            ]
            return "\n".join(lines) + "\n"
        except (BODParseError, BODStructureError) as e:
            if raise_on_error:
                raise
            return json.dumps({"status": "error", "message": str(e)}) + "\n"

    def from_json(
        self, data: Any, verb: str = "Sync", noun: Optional[str] = None, **kwargs: Any
    ) -> str:
        """Build BOD XML from JSON (reverse conversion); see ``json_to_bod``.

        Uses this converter's separator, max_size, and max_depth.
        """
        from .reverse import json_to_bod

        kwargs.setdefault("separator", self.separator)
        kwargs.setdefault("max_size", self.max_size)
        kwargs.setdefault("max_depth", self.max_depth)
        return json_to_bod(data, verb, noun, **kwargs)

    def convert(self, bod_xml: Union[str, bytes], verb: str) -> str:
        """Legacy method. Emits DeprecationWarning and calls to_json()."""
        warnings.warn(
            "The 'convert' function is deprecated and will be removed in v3.0.0. "
            "Use 'to_json' or 'to_ndjson' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.to_json(bod_xml, verb)


# -------------------------------------------------------------------
# Top-Level Facade Functions
# -------------------------------------------------------------------
def to_json(
    bod_xml: Union[str, bytes],
    verb: str,
    raise_on_error: bool = False,
    rules: Optional[RulesLike] = None,
) -> str:
    """Primary API for Standard JSON conversion (first noun only)."""
    return BODConverter().to_json(bod_xml, verb, raise_on_error=raise_on_error, rules=rules)


def to_ndjson(
    bod_xml: Union[str, bytes],
    verb: str,
    raise_on_error: bool = False,
    rules: Optional[RulesLike] = None,
    include_header: bool = False,
) -> str:
    """Primary API for NDJSON conversion (all nouns)."""
    return BODConverter().to_ndjson(
        bod_xml, verb, raise_on_error=raise_on_error, rules=rules, include_header=include_header
    )


def to_records(
    bod_xml: Union[str, bytes],
    verb: str,
    include_header: bool = False,
    rules: Optional[RulesLike] = None,
) -> List[Dict[str, Any]]:
    """Converts OAGIS XML into a native Python list of flattened dictionaries."""
    return BODConverter().to_records(bod_xml, verb, include_header=include_header, rules=rules)


def project(
    bod_xml: Union[str, bytes],
    verb: str,
    schema: Dict[str, Any],
    include_header: bool = True,
    coerce_booleans: bool = True,
    rules: Optional[RulesLike] = None,
) -> List[Dict[str, Any]]:
    """Extracts and maps OAGIS XML records directly into a target schema dictionary."""
    return BODConverter().project(
        bod_xml,
        verb,
        schema,
        include_header=include_header,
        coerce_booleans=coerce_booleans,
        rules=rules,
    )


def convert(bod_xml: Union[str, bytes], verb: str) -> str:
    """
    LEGACY FUNCTION: Maintained for backward compatibility.
    Maps to to_json() and emits DeprecationWarning.
    """
    warnings.warn(
        "The 'convert' function is deprecated and will be removed in v3.0.0. "
        "Use 'to_json' or 'to_ndjson' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return to_json(bod_xml, verb)
