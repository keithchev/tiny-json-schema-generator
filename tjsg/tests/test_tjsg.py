import copy

import deepdiff
import jsonschema
import pytest

from tjsg import JSONSchemaPrimitiveType, compile_schema, jst

# the schema validator to use
check_schema = jsonschema.validators.Draft7Validator.check_schema


def diff_schemas(schema1, schema2):
    return deepdiff.DeepDiff(schema1, schema2, ignore_order=True)


def test_json_primitive_type_compile():
    '''
    Test that the primitive types compile to the correct schema
    '''

    # a literal type
    schema = JSONSchemaPrimitiveType('number').compile()
    assert not diff_schemas(schema, {'type': 'number'})

    # union type
    schema = JSONSchemaPrimitiveType(['number', 'null']).compile()
    assert not diff_schemas(schema, {'type': ['null', 'number']})

    # array type
    schema = JSONSchemaPrimitiveType('array', items='string').compile()
    assert not diff_schemas(schema, {'type': 'array', 'items': {'type': 'string'}})

    # array of a union type
    schema = JSONSchemaPrimitiveType('array', items=['number', 'null']).compile()
    assert not diff_schemas(schema, {'type': 'array', 'items': {'type': ['number', 'null']}})

    # array of a union type defined by a PrimitiveType instance
    number_or_null = JSONSchemaPrimitiveType(['number', 'null'])
    schema = JSONSchemaPrimitiveType('array', items=number_or_null).compile()
    assert not diff_schemas(schema, {'type': 'array', 'items': {'type': ['null', 'number']}})

    # invalid primitive type
    with pytest.raises(ValueError):
        JSONSchemaPrimitiveType('uhoh')

    # compound type that includes an invalid primitive type
    with pytest.raises(ValueError):
        JSONSchemaPrimitiveType(['number', 'uhoh'])

    # `items` argument is array-specific
    with pytest.raises(ValueError):
        JSONSchemaPrimitiveType('number', items='number')

    # array type with invalid items
    with pytest.raises(ValueError):
        JSONSchemaPrimitiveType('array', items='uhoh')


def test_jst():
    '''
    Test that the pre-defined composite-type schemas compile correctly
    '''

    # a literal type
    schema = jst.number.compile()
    assert not diff_schemas(schema, {'type': 'number'})

    # a union type
    schema = jst.number_or_null.compile()
    assert not diff_schemas(schema, {'type': ['null', 'number']})

    # a larger union type
    schema = jst.number_or_string_or_boolean.compile()
    assert not diff_schemas(schema, {'type': ['string', 'number', 'boolean']})

    # array of a literal type
    schema = jst.string_array.compile()
    assert not diff_schemas(schema, {'type': 'array', 'items': {'type': 'string'}})

    # array of a union type
    schema = jst.number_or_null_array.compile()
    assert not diff_schemas(schema, {'type': 'array', 'items': {'type': ['number', 'null']}})

    # literal type with additional properties, set both at and after instantiation
    schema = jst.number(minimum=10, maximum=100)(multipleOf=3).compile()
    assert not diff_schemas(
        schema, {'type': 'number', 'minimum': 10, 'maximum': 100, 'multipleOf': 3}
    )

    invalid_types = ['bool', 'num_or_string', 'number_or_number', 'number_and_string']
    for invalid_type in invalid_types:
        with pytest.raises(AttributeError):
            getattr(jst, invalid_type)


def test_compile_schema():
    '''
    Test the schema compilation
    '''

    # schema with literal types, array type, and sub-schema type
    schema = {
        'sample_id': jst.number(minimum=0),
        'sample_name': jst.string_or_null,
        'data': [jst.number],
        'is_public': jst.boolean_or_null,
        'metadata': {
            'abundance': jst.number,
            'uniprot_id': jst.string,
            'names': {'gene': jst.string, 'protein': jst.string},
        },
    }
    expected_compiled_schema = {
        'type': 'object',
        'properties': {
            'sample_id': {'type': 'number', 'minimum': 0},
            'sample_name': {'type': ['string', 'null']},
            'data': {'type': 'array', 'items': {'type': 'number'}},
            'is_public': {'type': ['boolean', 'null']},
            'metadata': {
                'type': 'object',
                'properties': {
                    'abundance': {'type': 'number'},
                    'uniprot_id': {'type': 'string'},
                    'names': {
                        'type': 'object',
                        'properties': {'gene': {'type': 'string'}, 'protein': {'type': 'string'}},
                        '$defs': {},
                    },
                },
                '$defs': {},
            },
        },
        '$defs': {},
    }
    compiled_schema = compile_schema(schema)
    check_schema(compiled_schema)
    assert not diff_schemas(compiled_schema, expected_compiled_schema)

    # schema with a property whose type is an array of dicts
    schema = {
        'sample_name': jst.string_or_null,
        'data': [{'x': jst.number, 'y': jst.number}],
    }
    expected_compiled_schema = {
        'type': 'object',
        'properties': {
            'sample_name': {'type': ['string', 'null']},
            'data': {'type': 'array', 'items': {'$ref': '#/$defs/data'}},
        },
        '$defs': {
            'data': {
                'type': 'object',
                'properties': {'x': {'type': 'number'}, 'y': {'type': 'number'}},
            }
        },
    }
    compiled_schema = compile_schema(schema)
    check_schema(compiled_schema)
    assert not diff_schemas(compiled_schema, expected_compiled_schema)

    # schema with nested arrays of dicts
    schema = {
        'sample_name': jst.string_or_null,
        'datasets': [
            {
                'dataset_id': jst.number_or_null,
                'data': [{'x': jst.number, 'y': jst.number}],
            }
        ],
    }
    expected_compiled_schema = {
        'type': 'object',
        'properties': {
            'sample_name': {'type': ['string', 'null']},
            'datasets': {'type': 'array', 'items': {'$ref': '#/$defs/datasets'}},
        },
        '$defs': {
            'data': {
                'type': 'object',
                'properties': {
                    'x': {'type': 'number'},
                    'y': {'type': 'number'},
                },
            },
            'datasets': {
                'type': 'object',
                'properties': {
                    'dataset_id': {'type': ['number', 'null']},
                    'data': {'type': 'array', 'items': {'$ref': '#/$defs/data'}},
                },
            },
        },
    }
    compiled_schema = compile_schema(schema)
    check_schema(compiled_schema)
    assert not diff_schemas(compiled_schema, expected_compiled_schema)


def test_compile_top_level_arrays():

    # schema with a top-level array of dicts
    schema = [
        {
            'sample_name': jst.string_or_null,
            'data': [{'x': jst.number, 'y': jst.number}],
        }
    ]

    expected_compiled_schema = {
        'type': 'array',
        'items': {'$ref': '#/$defs/top_level_array_element'},
        '$defs': {
            'top_level_array_element': {
                'type': 'object',
                'properties': {
                    'sample_name': {'type': ['string', 'null']},
                    'data': {'type': 'array', 'items': {'$ref': '#/$defs/data'}},
                },
            },
            'data': {
                'type': 'object',
                'properties': {'x': {'type': 'number'}, 'y': {'type': 'number'}},
            },
        },
    }
    compiled_schema = compile_schema(schema)
    check_schema(compiled_schema)
    assert not diff_schemas(compiled_schema, expected_compiled_schema)


def test_compile_schema_errors():
    '''
    Tests for expected exceptions when compiling ill-formed schemas
    '''
    # schema with more than one element in an array type
    schema = {'name': jst.string_or_null, 'data': [jst.number, jst.string]}
    with pytest.raises(ValueError):
        compile_schema(schema)

    # schema with duplicated sub-schema-typed properties (the 'data' properties)
    schema = {
        'name': jst.string_or_null,
        'data': [
            {
                'dataset_id': jst.number,
                'data': [{'x': jst.number(maximum=0), 'y': jst.number(maximum=0)}],
            }
        ],
    }
    with pytest.raises(ValueError):
        compile_schema(schema)


def test_schema_validation():
    '''
    Test that a schema defined with the primitive types behaves as expected
    when compiled to the json-schema format and used with jsonschema to validate instances
    '''

    # top-level array of a primitive
    schema = [jst.number_or_null]
    valid_instance = [0, 1, 2, None]
    invalid_instance = [0, '0']

    jsonschema.validate(valid_instance, compile_schema(schema, require_all=True))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_instance, compile_schema(schema))

    # top-level array of dicts
    schema = [{'x': jst.number}]
    valid_instance = [{'x': 0}, {'x': 1}]
    invalid_instance = [{'x': '0'}]

    jsonschema.validate(valid_instance, compile_schema(schema, require_all=True))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_instance, compile_schema(schema))

    # complex schema with nested arrays of dicts
    schema = {
        'sample_id': jst.number_or_null,
        'sample_names': [jst.string_or_null],
        'datasets': [
            {
                'id': jst.number_or_null,
                'values': [{'x': jst.number(minimum=0), 'y': jst.number}],
            }
        ],
    }
    valid_instance = {
        'sample_id': 123,
        'sample_names': ['sample1', None],
        'datasets': [
            {'id': 0, 'values': [{'x': 0, 'y': 0}]},
            {'id': 1, 'values': [{'x': 0, 'y': 0}]},
        ],
    }
    jsonschema.validate(valid_instance, compile_schema(schema, require_all=True))

    # invalid sample_name
    invalid_instance = copy.deepcopy(valid_instance)
    invalid_instance['sample_names'][0] = 123
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_instance, compile_schema(schema))

    # invalid 'x' value
    invalid_instance = copy.deepcopy(valid_instance)
    invalid_instance['datasets'][0]['values'][0]['x'] = -111
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_instance, compile_schema(schema))

    # drop the 'id' property in the first dataset
    instance_missing_property = copy.deepcopy(valid_instance)
    instance_missing_property['datasets'][0].pop('id')

    # the instance with a missing 'id' property is still valid,
    # because jsonschema properties are optional by default
    jsonschema.validate(instance_missing_property, compile_schema(schema))

    # the instance is not valid if all properties are required
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance_missing_property, compile_schema(schema, require_all=True))
