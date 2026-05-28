import xml.etree.ElementTree as ET
import xmltodict
import json
import re
import warnings
from typing import Dict, Any

class BODConverter:
    def __init__(self, pnode: str = 'DataArea', separator: str = '_'):
        self.pnode = pnode
        self.separator = separator

    def _prepare_raw_dict(self, bod_xml: str, verb: str) -> Dict[str, Any]:
        """Internal helper to clean XML, strip verbs, and extract the raw dictionary."""
        clean_xml = bod_xml.strip().encode('utf-8').decode('utf-8-sig')
        sanitized_xml = re.sub(r'\sxmlns(?::\w+)?="[^"]+"', '', clean_xml, count=1)
        
        root = ET.fromstring(sanitized_xml)
        data_area = root.find(f".//{self.pnode}")
        
        if data_area is None:
            raise ValueError(f"Target node '{self.pnode}' not found.")

        verb_node = data_area.find(verb)
        if verb_node is not None:
            data_area.remove(verb_node)

        noun_node = list(data_area)[0]
        xml_fragment = ET.tostring(noun_node, encoding='utf-8').decode('utf-8')
        
        return xmltodict.parse(xml_fragment)

    def _flatify(self, obj: Any, prefix: str = "") -> Dict[str, Any]:
        """Recursively flattens deeply nested structures into single-level key-values."""
        flat_dict = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_key = f"{prefix}{self.separator}{k}" if prefix else k
                flat_dict.update(self._flatify(v, new_key))
        elif isinstance(obj, (list, tuple)):
            for i, v in enumerate(obj):
                new_key = f"{prefix}{self.separator}{i}"
                flat_dict.update(self._flatify(v, new_key))
        else:
            flat_dict[prefix] = obj
        return flat_dict

    def to_json(self, bod_xml: str, verb: str) -> str:
        """Converts OAGIS XML to a single, standard flat JSON string."""
        try:
            raw_dict = self._prepare_raw_dict(bod_xml, verb)
            flattened = self._flatify(raw_dict)
            return json.dumps(flattened)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def to_ndjson(self, bod_xml: str, verb: str) -> str:
        """
        Converts OAGIS XML into strict NDJSON format.
        Flattens and compresses individual objects onto single lines terminated by a newline.
        """
        try:
            raw_dict = self._prepare_raw_dict(bod_xml, verb)
            noun_key = list(raw_dict.keys())[0]
            noun_content = raw_dict[noun_key]

            if isinstance(noun_content, list):
                lines = []
                for record in noun_content:
                    flat_record = self._flatify({noun_key: record})
                    compact_line = json.dumps(flat_record, separators=(',', ':')).strip()
                    lines.append(compact_line)
                return "\n".join(lines) + "\n"
            
            flat_record = self._flatify(raw_dict)
            compact_line = json.dumps(flat_record, separators=(',', ':')).strip()
            return compact_line + "\n"

        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}) + "\n"

    def convert(self, bod_xml: str, verb: str) -> str:
        """Legacy class method kept for 100% backward compatibility."""
        return self.to_json(bod_xml, verb)


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