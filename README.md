# Mapper

Mapper is a python library to convert the Infor OAGIS BODs to Flattened JSON.
The library simplifies the converted JSON by keeping only the content within DataArea.
The library will remove the Verb node from DataArea and keeps only the Noun node.

#### Usage

##### Getting it
To download BODtoJSON, either fork this github repo or simply use Pypi via pip.
```python
$ pip install BODtoJSON
```
##### Using it:
```python
from BODtoJSON.BODtoJSON import convert
output_var = convert(input_var)
```

# MIT License
Read License.txt
