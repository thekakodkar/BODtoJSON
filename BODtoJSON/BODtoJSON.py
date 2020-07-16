# Copyright (c) 2020 Niraj Kakodkar
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


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
