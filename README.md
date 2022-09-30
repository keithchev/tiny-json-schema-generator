# Tiny JSON schema generator

This is a Python package that provides a compact way to define JSON schemas. Here is an example:
```
schema = {
    'cell_line_id': jst.number,
    'published': jst.boolean_or_null,
    'names': [jst.string_or_null],
    'data': [
        {
            'dataset_id': jst.number_or_null,
            'values': [{'x': jst.number(maximum=1), 'y': jst.number(maximum=1)],
        },
    ]
}
```
where `jst` are pre-defined types. 

This compact representation is then compiled to its jsonschema-compliant form:
```
{
    "type": "object",
    "properties": {
        "cell_line_id": {
            "type": ["number", "null"],
            "minimum": 10
        },
        "names": {
            "type": "array",
            "items": {
                "type": ["string", "null"]
            }
        },
        "data": {
            "type": "array",
            "items": {"$ref": "#/$defs/data"}
        }
    },
    "$defs": {
        "data": {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": ["number", "null"]
                },
                "value": {
                    "type": "array",
                    "items": {"type": "number", "maximum": 1}
                }
            },
            "$defs": {}
        }
    }
}
```


## Install
```
conda create -y -n tjsgenv python=3.9
pip install -e '[dev]'
```

Run tests:
```
pytest -v
```
