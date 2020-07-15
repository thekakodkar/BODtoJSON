import xmltodict, json
from flatten_json import flatten_json
from pandas import json_normalize

## Remove the below line while using in the ION Script
from config import config

##

# Change the config.input_var to input_var while using in ION Script
output_var = xmltodict.parse(config.input_var)

# output_var = json.dumps(json.loads(output_var), indent=4)
flat = flatten_json(output_var)
json_normalize(flat)

## Remove the below line while using in the ION Script
print(output_var)
##
