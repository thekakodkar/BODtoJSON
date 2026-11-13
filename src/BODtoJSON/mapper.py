import xml.etree.ElementTree as ET
import json
import re
import warnings
from typing import Dict, Any, List, Optional


class BODConverter:
    def __init__(self, pnode: str = 'DataArea', separator: str = '_'):
        self.pnode = pnode
        self.separator = separator

    def _prepare_noun_element(self, bod_xml: str, verb: str) -> ET.Element:
        """Cleans XML, strips the administrative Verb, and extracts the primary Noun element."""
        clean_xml = bod_xml.strip().encode('utf-8').decode('utf-8-sig')
        sanitized_xml = re.sub(r'\sxmlns(?::\w+)?="[^"]+"', '', clean_xml, count=1)

        root = ET.fromstring(sanitized_xml)
        data_area = root.find(f".//{self.pnode}")

        if data_area is None:
            raise ValueError(f"Target node '{self.pnode}' not found.")

        verb_node = data_area.find(verb)
        if verb_node is not None:
            data_area.remove(verb_node)

        children = list(data_area)
        if not children:
            raise ValueError(f"No Noun element found inside '{self.pnode}'.")

        return children[0]

    def _strip_ns(self, tag: str) -> str:
        """Strips any residual {namespace} URI prefixes from ElementTree tags."""
        return tag.split('}', 1)[-1] if '}' in tag else tag

    def _flatten_element(self, elem: ET.Element, prefix: str = "") -> Dict[str, Any]:
        """
        Recursively traverses an ElementTree node directly into a flattened dictionary,
        preserving exact attribute (@) and text (#text) key parity.
        """
        flat_dict: Dict[str, Any] = {}
        tag_name = self._strip_ns(elem.tag)
        current_prefix = f"{prefix}{self.separator}{tag_name}" if prefix else tag_name

        # 1. Extract XML Attributes (e.g., _@accountingEntity)
        for attr_k, attr_v in elem.attrib.items():
            clean_attr = self._strip_ns(attr_k)
            flat_dict[f"{current_prefix}{self.separator}@{clean_attr}"] = attr_v

        children = list(elem)
        text_val = elem.text.strip() if elem.text and elem.text.strip() else None

        # 2. Leaf Node Handling
        if not children:
            if elem.attrib:
                if text_val is not None:
                    flat_dict[f"{current_prefix}{self.separator}#text"] = text_val
            else:
                flat_dict[current_prefix] = text_val
            return flat_dict

        # 3. Mixed Content Handling (Parent node has children AND direct text)
        if text_val is not None:
            flat_dict[f"{current_prefix}{self.separator}#text"] = text_val

        # 4. Group Child Elements by Tag Name to Detect Repeating Arrays
        grouped_children: Dict[str, List[ET.Element]] = {}
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

    def _flatten_indexed_child(self, elem: ET.Element, indexed_prefix: str) -> Dict[str, Any]:
        """Helper to flatten elements inside a repeating sibling list without duplicating the tag name."""
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

        grouped_children: Dict[str, List[ET.Element]] = {}
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

    def _extract_header_context(self, root: ET.Element, verb_node: Optional[ET.Element]) -> Dict[str, Any]:
        """Captures ApplicationArea and Verb metadata before the Verb node is stripped."""
        context: Dict[str, Any] = {}
        app_area = root.find(".//ApplicationArea")
        if app_area is not None:
            context.update(self._flatten_element(app_area))
        if verb_node is not None:
            context.update(self._flatten_element(verb_node))
        return context

    def to_records(self, bod_xml: str, verb: str, include_header: bool = False) -> List[Dict[str, Any]]:
        """
        Parses OAGIS XML directly into a native Python list of flattened dictionaries.
        Raises ValueError on malformed XML or missing nodes.
        """
        clean_xml = bod_xml.strip().encode('utf-8').decode('utf-8-sig')
        sanitized_xml = re.sub(r'\sxmlns(?::\w+)?="[^"]+"', '', clean_xml, count=1)

        root = ET.fromstring(sanitized_xml)
        data_area = root.find(f".//{self.pnode}")

        if data_area is None:
            raise ValueError(f"Target node '{self.pnode}' not found.")

        verb_node = data_area.find(verb)
        header_context = self._extract_header_context(root, verb_node) if include_header else {}

        if verb_node is not None:
            data_area.remove(verb_node)

        noun_nodes = list(data_area)
        if not noun_nodes:
            raise ValueError(f"No Noun element found inside '{self.pnode}'.")

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
        coerce_booleans: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Extracts records and projects them into a target API/ERP JSON schema in one step.
        Schema values can be:
          - Template strings with {Key_Name} placeholders (e.g., "company[{Sync_AccountingEntityID}]")
          - Direct key strings (e.g., "ChartOfAccounts_BaseChartOfAccounts_GLNominalAccount")
          - Callables receiving the flattened record dict
          - Literal constants (bool, int, float, None)
        """
        records = self.to_records(bod_xml, verb, include_header=include_header)
        projected_items: List[Dict[str, Any]] = []

        class _SafeDict(dict):
            def __missing__(self, key):
                return ""

        for rec in records:
            clean_rec = _SafeDict({k: ("" if v is None else str(v).strip()) for k, v in rec.items()})
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

    def to_json(self, bod_xml: str, verb: str) -> str:
        """Converts OAGIS XML to a single, standard flat JSON string."""
        try:
            noun_elem = self._prepare_noun_element(bod_xml, verb)
            flattened = self._flatten_element(noun_elem)
            return json.dumps(flattened)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def to_ndjson(self, bod_xml: str, verb: str) -> str:
        """
        Converts OAGIS XML into strict NDJSON format.
        Unpacks repeating sibling elements under DataArea into single-line records.
        """
        try:
            records = self.to_records(bod_xml, verb, include_header=False)
            lines = [json.dumps(rec, separators=(',', ':')).strip() for rec in records]
            return "\n".join(lines) + "\n"
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}) + "\n"

    def convert(self, bod_xml: str, verb: str) -> str:
        """Legacy class method kept for 100% backward compatibility."""
        warnings.warn(
            "The 'convert' function is deprecated and will be removed in v3.0.0. Use 'to_json' or 'to_ndjson' instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.to_json(bod_xml, verb)


# -------------------------------------------------------------------
# Top-Level Facade Functions (Global Access Shorthand)
# -------------------------------------------------------------------
def to_json(bod_xml: str, verb: str) -> str:
    """Primary API for Standard JSON conversion."""
    return BODConverter().to_json(bod_xml, verb)


def to_ndjson(bod_xml: str, verb: str) -> str:
    """Primary API for Newline Delimited JSON (NDJSON) conversion."""
    return BODConverter().to_ndjson(bod_xml, verb)


def to_records(bod_xml: str, verb: str, include_header: bool = False) -> List[Dict[str, Any]]:
    """Converts OAGIS XML into a native Python list of flattened dictionaries."""
    return BODConverter().to_records(bod_xml, verb, include_header=include_header)


def project(
    bod_xml: str,
    verb: str,
    schema: Dict[str, Any],
    include_header: bool = True,
    coerce_booleans: bool = True
) -> List[Dict[str, Any]]:
    """Extracts and maps OAGIS XML records directly into a target schema dictionary."""
    return BODConverter().project(
        bod_xml,
        verb,
        schema,
        include_header=include_header,
        coerce_booleans=coerce_booleans
    )


def convert(bod_xml: str, verb: str) -> str:
    """
    LEGACY FUNCTION: Maintained to prevent breaking production changes.
    Maps directly to to_json() behind the scenes.
    """
    warnings.warn(
        "The 'convert' function is deprecated and will be removed in v3.0.0. Use 'to_json' or 'to_ndjson' instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return to_json(bod_xml, verb)