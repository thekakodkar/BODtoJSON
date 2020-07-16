import xmltodict, json
import xml.etree.ElementTree as ET
import re
from flatten_json import flatten_json


def convert(input_var):
    # Remove Namespaces from XML
    input = re.sub(' xmlns="[^"]+"', '', input_var, count=1)

    # Create an Element Tree
    root = ET.fromstring(input)

    # Extract the Data Area
    # Remove unnecessary Nodes
    for parentnode in root.findall('DataArea'):
        for node in parentnode.findall('Sync'):
            parentnode.remove(node)
        root = ET.tostring(parentnode).decode('utf-8')

    output_var = xmltodict.parse(root)
    output_var = flatten_json(output_var)
    output_var = json.dumps(output_var)
    return (output_var)
