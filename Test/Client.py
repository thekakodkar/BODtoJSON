from config import config
from BODtoJSON.BODtoJSON import convert

output_var = convert(config.input_var)
print(output_var)
