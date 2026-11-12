import xml.etree.ElementTree as ET
import json
import re
import warnings
from typing import Dict, Any, List, Tuple


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
        preserving exact xmltodict attribute (@) and text (#text) key parity.
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
                # If node has both attributes and text, assign text to _#text
                if text_val is not None:
                    flat_dict[f"{current_prefix}{self.separator}#text"] = text_val
            else:
                # Pure text leaf node (maps to None if empty, matching xmltodict parity)
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
                # Repeating sibling tags get indexed (e.g., _PurchaseOrderLine_0_...)
                for idx, child_elem in enumerate(c_list):
                    indexed_prefix = f"{current_prefix}{self.separator}{c_tag}{self.separator}{idx}"
                    # Process attributes and children of the indexed element directly
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
            clean_xml = bod_xml.strip().encode('utf-8').decode('utf-8-sig')
            sanitized_xml = re.sub(r'\sxmlns(?::\w+)?="[^"]+"', '', clean_xml, count=1)

            root = ET.fromstring(sanitized_xml)
            data_area = root.find(f".//{self.pnode}")

            if data_area is None:
                raise ValueError(f"Target node '{self.pnode}' not found.")

            verb_node = data_area.find(verb)
            if verb_node is not None:
                data_area.remove(verb_node)

            noun_nodes = list(data_area)
            if not noun_nodes:
                raise ValueError(f"No Noun element found inside '{self.pnode}'.")

            lines = []
            for noun_elem in noun_nodes:
                flat_record = self._flatten_element(noun_elem)
                compact_line = json.dumps(flat_record, separators=(',', ':')).strip()
                lines.append(compact_line)

            return "\n".join(lines) + "\n"

        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}) + "\n"

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


# -------------------------------------------------------------------
# Top-Level Facade Functions (Global Access Shorthand)
# -------------------------------------------------------------------
def to_json(bod_xml: str, verb: str) -> str:
    """Primary API for Standard JSON conversion"""
    return BODConverter().to_json(bod_xml, verb)


def to_ndjson(bod_xml: str, verb: str) -> str:
    """Primary API for Newline Delimited JSON (NDJSON) conversion"""
    return BODConverter().to_ndjson(bod_xml, verb)


def convert(bod_xml: str, verb: str) -> str:
    """
    LEGACY FUNCTION: Maintained to prevent breaking production changes.
    Maps directly to to_json() behind the scenes.
    """
    warnings.warn(
        "The 'convert' function is deprecated and will be removed in v2.0.0. Use 'to_json' or 'to_ndjson' instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return to_json(bod_xml, verb)