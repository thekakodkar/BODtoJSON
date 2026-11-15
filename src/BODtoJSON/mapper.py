import json
import warnings
from typing import Dict, Any, List, Optional

try:
    from defusedxml.ElementTree import fromstring as safe_fromstring
except ImportError:
    # Fallback only for environments without the dep (should not happen in normal use)
    from xml.etree.ElementTree import fromstring as safe_fromstring


class BODParseError(Exception):
    """Raised for malformed XML, entity expansion rejection, or oversize documents."""


class BODStructureError(ValueError):
    """Raised for missing DataArea, verb, or noun elements."""


class BODConverter:
    """Safe, namespace-aware OAGIS BOD to flattened JSON converter."""

    DEFAULT_MAX_SIZE = 10 * 1024 * 1024  # 10 MiB

    def __init__(
        self,
        pnode: str = "DataArea",
        separator: str = "_",
        max_size: Optional[int] = None,
    ):
        self.pnode = pnode
        self.separator = separator
        self.max_size = max_size if max_size is not None else self.DEFAULT_MAX_SIZE

    def _check_size(self, bod_xml: str) -> None:
        if len(bod_xml.encode("utf-8")) > self.max_size:
            raise BODParseError(
                f"Document exceeds maximum allowed size of {self.max_size} bytes."
            )

    def _parse(self, bod_xml: str):
        """Parse XML safely with defusedxml and return the root element."""
        self._check_size(bod_xml)
        clean_xml = bod_xml.strip().encode("utf-8").decode("utf-8-sig")
        try:
            return safe_fromstring(clean_xml)
        except Exception as e:
            raise BODParseError(f"Failed to parse XML: {e}") from e

    def _find_local(self, elem, local_name: str):
        """Find first element with the given local name, ignoring namespaces."""
        if elem is None:
            return None
        # ElementTree {*} wildcard is supported since Python 3.8
        found = elem.find(f".//{{*}}{local_name}")
        if found is not None:
            return found
        # Also check the element itself
        tag = elem.tag
        local = tag.split("}", 1)[-1] if "}" in tag else tag
        if local == local_name:
            return elem
        return None

    def _prepare_noun_element(self, bod_xml: str, verb: str):
        """Extract the first noun under DataArea after removing the verb."""
        root = self._parse(bod_xml)
        data_area = self._find_local(root, self.pnode)
        if data_area is None:
            raise BODStructureError(f"Target node '{self.pnode}' not found.")

        verb_node = self._find_local(data_area, verb)
        if verb_node is None:
            raise BODStructureError(f"Verb '{verb}' not found under '{self.pnode}'.")

        data_area.remove(verb_node)

        children = list(data_area)
        if not children:
            raise BODStructureError(f"No Noun element found inside '{self.pnode}'.")

        return children[0]

    def _strip_ns(self, tag: str) -> str:
        """Strips any residual {namespace} URI prefixes from ElementTree tags."""
        return tag.split("}", 1)[-1] if "}" in tag else tag

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
        self, bod_xml: str, verb: str, include_header: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Parses OAGIS XML into a list of flattened dictionaries (one per noun).
        Raises BODParseError or BODStructureError on failure.
        """
        root = self._parse(bod_xml)
        data_area = self._find_local(root, self.pnode)
        if data_area is None:
            raise BODStructureError(f"Target node '{self.pnode}' not found.")

        verb_node = self._find_local(data_area, verb)
        if verb_node is None:
            raise BODStructureError(f"Verb '{verb}' not found under '{self.pnode}'.")

        header_context = (
            self._extract_header_context(root, verb_node) if include_header else {}
        )

        data_area.remove(verb_node)

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

        return records

    def project(
        self,
        bod_xml: str,
        verb: str,
        schema: Dict[str, Any],
        include_header: bool = True,
        coerce_booleans: bool = True,
    ) -> List[Dict[str, Any]]:
        """Projects flattened records into a target schema."""
        records = self.to_records(bod_xml, verb, include_header=include_header)
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
        self, bod_xml: str, verb: str, raise_on_error: bool = False
    ) -> str:
        """
        Converts OAGIS XML to a single flat JSON string (first noun only).

        By default returns an error JSON object on failure (backward compatible).
        Set raise_on_error=True to raise BODParseError / BODStructureError instead.
        """
        try:
            noun_elem = self._prepare_noun_element(bod_xml, verb)
            flattened = self._flatten_element(noun_elem)
            return json.dumps(flattened)
        except (BODParseError, BODStructureError) as e:
            if raise_on_error:
                raise
            return json.dumps({"status": "error", "message": str(e)})

    def to_ndjson(
        self, bod_xml: str, verb: str, raise_on_error: bool = False
    ) -> str:
        """
        Converts OAGIS XML into NDJSON (one record per noun).

        Default returns error JSON on failure. raise_on_error=True raises.
        """
        try:
            records = self.to_records(bod_xml, verb, include_header=False)
            lines = [
                json.dumps(rec, separators=(",", ":")).strip() for rec in records
            ]
            return "\n".join(lines) + "\n"
        except (BODParseError, BODStructureError) as e:
            if raise_on_error:
                raise
            return json.dumps({"status": "error", "message": str(e)}) + "\n"

    def convert(self, bod_xml: str, verb: str) -> str:
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
def to_json(bod_xml: str, verb: str, raise_on_error: bool = False) -> str:
    """Primary API for Standard JSON conversion (first noun only)."""
    return BODConverter().to_json(bod_xml, verb, raise_on_error=raise_on_error)


def to_ndjson(bod_xml: str, verb: str, raise_on_error: bool = False) -> str:
    """Primary API for NDJSON conversion (all nouns)."""
    return BODConverter().to_ndjson(bod_xml, verb, raise_on_error=raise_on_error)


def to_records(
    bod_xml: str, verb: str, include_header: bool = False
) -> List[Dict[str, Any]]:
    """Converts OAGIS XML into a native Python list of flattened dictionaries."""
    return BODConverter().to_records(bod_xml, verb, include_header=include_header)


def project(
    bod_xml: str,
    verb: str,
    schema: Dict[str, Any],
    include_header: bool = True,
    coerce_booleans: bool = True,
) -> List[Dict[str, Any]]:
    """Extracts and maps OAGIS XML records directly into a target schema dictionary."""
    return BODConverter().project(
        bod_xml,
        verb,
        schema,
        include_header=include_header,
        coerce_booleans=coerce_booleans,
    )


def convert(bod_xml: str, verb: str) -> str:
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
