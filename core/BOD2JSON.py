import xmltodict, json

## Remove the below line while using in the ION Script
from config import config

##

# Change the config.input_var to input_var while using in ION Script
output_var = xmltodict.parse(config.input_var)
output_var = json.dumps(output_var)

output_var = json.dumps(json.loads(output_var), indent=4)

## Remove the below line while using in the ION Script
print(output_var)
##
