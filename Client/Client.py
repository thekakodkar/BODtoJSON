from config import config
from BODtoFlatJSON import convert

output_var = convert(config.input_var)
print(output_var)
