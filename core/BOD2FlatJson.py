import xmltodict, json
from flatten_json import flatten_json

## Remove the below line while using in the ION Script
from config import config

##

# Change the config.input_var to input_var while using in ION Script
output_var = xmltodict.parse(config.input_var)

# output_var = json.dumps(json.loads(output_var), indent=4)
output_var = flatten_json(output_var)
output_var = json.dumps(output_var)

## Remove the below line while using in the ION Script
print(output_var)
##
