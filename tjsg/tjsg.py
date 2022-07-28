import dataclasses


class JSONSchemaPrimitiveType:

    valid_types = ['string', 'number', 'boolean', 'array', 'null']

    def __init__(self, types, items=None):

        if isinstance(types, str):
            types = [types]

        if isinstance(types, list):
            for type_ in types:
                if type_ not in self.valid_types:
                    raise ValueError("Invalid primitive type '%s'" % type_)
        else:
            raise TypeError(
                '`types` must be a list of strings or an instance of `JSONSchemaPrimitiveType`'
            )

        self.types = types

        if isinstance(items, JSONSchemaPrimitiveType):
            self.items = items
        elif items is not None:
            self.items = JSONSchemaPrimitiveType(types=items)
        else:
            self.items = None

        if self.items is not None and 'array' not in self.types:
            raise ValueError('items can only be specified for array types')

        # type-specific properties
        # TODO: validate these according to the json-schema spec
        self.props = {}

    def compile(self):
        ''' '''
        value = {'type': self.types[0] if len(self.types) == 1 else self.types}
        if self.items is not None:
            value['items'] = self.items.compile()

        value.update(self.props)
        return value

    def __repr__(self):
        s = ' or '.join(self.types)
        if self.items is not None:
            s += f'[{self.items}]'
        return s

    def __call__(self, **kwargs):
        self.props.update(kwargs)
        return self


class JSONSchemaTypes:
    '''
    Convenience method to instantiate primitive and common composite types

    Supports two composite types:
    1) unions of primitive types in the form of `{type1}_or_{type2}`
    2) arrays of unions in the form of `{type1}_array`

    Examples:
        JSONSchemaTypes().number
        JSONSchemaTypes().number_or_null
        JSONSchemaTypes().number_or_string_null
        JSONSchemaTypes().number_or_null_array
    '''

    def __getattr__(self, attr):

        if attr in JSONSchemaPrimitiveType.valid_types:
            type_args = (attr,)

        elif attr.endswith('_array'):
            items = attr.replace('_array', '').split('_or_')
            type_args = ('array', items)

        elif '_or_' in attr:
            types = attr.split('_or_')
            if len(set(types)) != len(types):
                raise AttributeError("Invalid composite type '%s'" % attr)
            type_args = (types,)
        else:
            raise AttributeError("Invalid composite type '%s'" % attr)

        try:
            primitive_type = JSONSchemaPrimitiveType(*type_args)
        except ValueError:
            raise AttributeError("Invalid composite type '%s'" % attr)

        return primitive_type


jst = JSONSchemaTypes()


@dataclasses.dataclass(init=False)
class KW:
    '''
    keywords in the JSON schema definition
    '''

    type = 'type'
    items = 'items'
    defs = '$defs'
    ref = '$ref'
    properties = 'properties'
    object = 'object'
    array = 'array'


def _require_all_properties(compiled_schema):
    '''
    Helper function to define all properties as required in the compiled schema
    '''
    property_names = compiled_schema.get('properties').keys()
    compiled_schema['required'] = list(property_names)
    for property_name in property_names:
        if compiled_schema['properties'][property_name].get('type') == 'object':
            _require_all_properties(compiled_schema['properties'][property_name])


def compile_schema(raw_schema, require_all=False, _schema_defs=None):
    '''
    Compile a raw schema into the json-schema format
    by moving the properties to a 'properties' dict,
    compiling the literal types,
    and adding a `'type': 'object'` to the top-level schemas and any nested schemas

    Note that the 'raw schema' means a literal dict whose values
    are instances of JSONSchemaPrimitiveType (or nested dicts of same)

    Example:
    '''

    if isinstance(raw_schema, JSONSchemaPrimitiveType):
        return raw_schema.compile()

    if isinstance(raw_schema, list):
        return _compile_array_schema(raw_schema, require_all=require_all)

    elif isinstance(raw_schema, dict):

        compiled_schema = {KW.type: KW.object, KW.properties: {}}

        # _schema_defs is None only for initial/top-level calls to `compile_schema`
        if _schema_defs is None:
            compiled_schema[KW.defs] = {}
            _schema_defs = compiled_schema[KW.defs]

        for property_name, property_schema in raw_schema.items():

            if isinstance(property_schema, JSONSchemaPrimitiveType):
                compiled_property_schema = property_schema.compile()

            elif isinstance(property_schema, list):
                compiled_property_schema = _compile_array_schema(
                    property_schema,
                    def_id=property_name,
                    schema_defs=_schema_defs,
                    require_all=require_all,
                )

            # if the property is itself an object schema
            else:
                compiled_property_schema = compile_schema(property_schema)

            compiled_schema[KW.properties][property_name] = compiled_property_schema

    if require_all:
        _require_all_properties(compiled_schema)

    return compiled_schema


def _compile_array_schema(raw_schema, def_id=None, schema_defs=None, require_all=False):
    ''' '''

    assert isinstance(raw_schema, list)

    # by definition, if the property is a list, then the property schema is an array
    # whose element schema is defined by the sole element in the list
    if len(raw_schema) != 1:
        raise ValueError('Array-typed property schemas must be a list with a single element')

    element_schema = raw_schema[0]
    element_schema_is_subschema = isinstance(element_schema, dict)

    # if the element schema is a primitive type
    if not element_schema_is_subschema:
        return JSONSchemaPrimitiveType(KW.array, items=element_schema).compile()

    # whether the array is the top level in the original raw schema
    # (instead of the schema of some property in the original raw schema)
    array_is_top_level = schema_defs is None
    if array_is_top_level:
        schema_defs = {}
        def_id = 'top_level_array_element'

    # if the element schema is an object schema, we need to define a sub-schema
    # and add its definition to the schema_defs
    compiled_schema = {KW.type: KW.array, KW.items: {KW.ref: f'#/{KW.defs}/{def_id}'}}

    # if the schema we are compiling is the top-level schema,
    # we need to include the schema defs
    if array_is_top_level:
        compiled_schema[KW.defs] = schema_defs

    # recursively compile the sub-schema
    schema_def = compile_schema(element_schema, _schema_defs=schema_defs, require_all=require_all)

    # check that the new sub-schema definition id is unique
    if def_id in schema_defs:
        raise ValueError('Object-typed property names must be globally unique')

    schema_defs[def_id] = schema_def

    return compiled_schema
