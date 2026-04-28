import xml.etree.ElementTree as ET
import xmltodict
import json
import re
from typing import Dict, Any

class BODConverter:
    def __init__(self, pnode: str = 'DataArea', separator: str = '_'):
        self.pnode = pnode
        self.separator = separator

    def convert(self, bod_xml: str, verb: str) -> str:
        try:
            # Defensive cleaning to handle BOM and namespaces
            clean_xml = bod_xml.strip().encode('utf-8').decode('utf-8-sig')
            sanitized_xml = re.sub(r'\sxmlns(?::\w+)?="[^"]+"', '', clean_xml, count=1)
            
            root = ET.fromstring(sanitized_xml)
            data_area = root.find(f".//{self.pnode}")
            
            if data_area is None:
                raise ValueError(f"Target node '{self.pnode}' not found.")

            # Remove administrative Verb (Sync/Process)
            verb_node = data_area.find(verb)
            if verb_node is not None:
                data_area.remove(verb_node)

            # Extract the Noun (the primary child of DataArea)
            # This prevents wrapping the JSON in a redundant 'DataArea' key
            noun_node = list(data_area)[0]
            xml_fragment = ET.tostring(noun_node, encoding='utf-8').decode('utf-8')
            
            raw_dict = xmltodict.parse(xml_fragment)
            return json.dumps(self._flatify(raw_dict))

        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def _flatify(self, obj: Any, prefix: str = "") -> Dict[str, Any]:
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

def convert(bod_xml: str, verb: str) -> str:
    """Primary API for BODtoJSON v1.0.0"""
    return BODConverter().convert(bod_xml, verb)