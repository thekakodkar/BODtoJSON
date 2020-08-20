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
pnode = 'DataArea'


def convert(bod, noun):
    """
    converts the input BOX XML to Flat JASON
    :param bod:
    :return: Flat JSON
    """
    # Remove Namespaces from XML
    input = re.sub(' xmlns="[^"]+"', '', bod, count=1)

    # Create an Element Tree
    root = ET.fromstring(input)

    # Extract the Data Area
    # Remove unnecessary Nodes
    for parentnode in root.findall(pnode):
        for node in parentnode.findall(noun):
            parentnode.remove(node)
        root = ET.tostring(parentnode).decode('utf-8')

    jsonout = xmltodict.parse(root)
    jsonout = flatify(jsonout)
    jsonout = json.dumps(jsonout)
    return (jsonout)


def _genkey(prev_key, separator, new_key):
    """
    Returns the new_key in case no prev key exists, concatenates
    prev key, separator, and new_key otherwise
    :param prev_key:
    :param separator:
    :param new_key:
    :return: a string if prev_key exists and simply passes through the
    new_key otherwise
    """
    if prev_key:
        return u"{}{}{}".format(prev_key, separator, new_key)
    else:
        return new_key


def flatify(idict, separator="_", root_keys_to_ignore=set()):
    """
    Creates flat dictionary from the nested dictionary

    :param idict: Nested dictionary we want to make flat
    :param separator: string to separate dictionary keys by
    :param root_keys_to_ignore: set of root keys to ignore from flattening
    :return: flat dictionary
    """
    assert isinstance(idict, dict), "flattify requires a dictionary input"
    assert isinstance(separator, str), "separator must be string"

    flat_dict = dict()

    def _flatify(object_, key):
        """
        :param object_: object to flatten
        :param key: carries the concatenated key for the object_
        :return: None
        """
        # Empty object can't be iterated, take as is
        if not object_:
            flat_dict[key] = object_
        # These object types support iteration
        elif isinstance(object_, dict):
            for object_key in object_:
                if not (not key and object_key in root_keys_to_ignore):
                    _flatify(object_[object_key], _genkey(key,
                                                          separator,
                                                          object_key))
        elif isinstance(object_, (list, set, tuple)):
            for index, item in enumerate(object_):
                _flatify(item, _genkey(key, separator, index))
        else:
            flat_dict[key] = object_

    _flatify(idict, None)
    return flat_dict
