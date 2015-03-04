import six


class Field(object):
    """Field base class"""

    def __init__(self, name=None, required=True, default=None):
        self._attr_name = None
        self._resource = None

        self.name = name
        self.required = required
        self.default = default

    def contribute_to_class(self, cls, name):
        self._attr_name = name
        self._resource = cls

        if not self.name:
            self.name = name

        cls._meta.fields.append(self)

    def to_python(self, value, resource):
        """Returns the value as returned by the serializer converted to a Python object"""

        return value

    def to_value(self, obj, resource):
        """Returns the Python object converted to a value ready for serialization"""

        return obj


class DictField(Field):
    """Same as base field. Aliased for semantic purposes."""

    pass


class TextField(Field):
    def __init__(self, encoding='utf-8', *args, **kwargs):
        super(TextField, self).__init__(*args, **kwargs)

        self.encoding = encoding

    def to_python(self, value, resource):
        """Converts to unicode if self.encoding != None, otherwise returns input without attempting to decode"""

        if isinstance(value, six.text_type):
            return value

        if self.encoding is None and isinstance(value, (six.text_type, six.binary_type)):
            return value

        if self.encoding is not None and isinstance(value, six.binary_type):
            return value.decode(self.encoding)

        return six.text_type(value)


class BooleanField(Field):
    def to_python(self, value, resource):
        return bool(value)


class NumberField(Field):
    def to_python(self, value, resource):
        if isinstance(value, (int, float)):
            return value

        number = float(value)
        return int(number) if number.is_integer() else number


class IntegerField(NumberField):
    def to_python(self, value, resource):
        return int(super(IntegerField, self).to_python(value, resource))

    def to_value(self, obj, resource):
        return int(obj)


class FloatField(NumberField):
    def to_python(self, value, resource):
        return float(super(FloatField, self).to_python(value, resource))

    def to_value(self, obj, resource):
        return float(obj)


class ObjectField(Field):
    """Represents a dictionary as a Python object (lists, too)"""

    def __init__(self, class_name='AnonymousObject', aliases={}, *args, **kwargs):
        self.class_name = class_name
        self.aliases = aliases
        self.reverse_aliases = {v: k for k, v in six.iteritems(aliases)}

        super(ObjectField, self).__init__(*args, **kwargs)

    def to_python(self, value, resource):
        """Dictionary to Python object"""

        if isinstance(value, dict):
            d = {
                self.aliases.get(k, k): self.to_python(v, resource) if isinstance(v, (dict, list)) else v
                for k, v in six.iteritems(value)
            }
            return type(self.class_name, (), d)
        elif isinstance(value, list):
            return [self.to_python(x, resource) if isinstance(x, (dict, list)) else x for x in value]
        else:
            return value

    def to_value(self, obj, resource, visited=set()):
        """Python object to dictionary"""

        if id(obj) in visited:
            raise ValueError('Circular reference detected when attempting to serialize object')

        if isinstance(obj, (list, tuple, set)):
            return [self.to_value(x, resource) if hasattr(x, '__dict__') else x for x in obj]
        elif hasattr(obj, '__dict__'):
            attrs = obj.__dict__.copy()
            for key in six.iterkeys(obj.__dict__):
                if key.startswith('_'):
                    del attrs[key]

            return {
                self.reverse_aliases.get(k, k):
                    self.to_value(v, resource) if hasattr(v, '__dict__') or isinstance(v, (list, tuple, set)) else v
                for k, v in six.iteritems(attrs)
            }
        else:
            return obj


class NestedResourceField(Field):
    """Base class for nested resource fields"""

    URI_ONLY = 'uri'
    PARTIAL_OBJECT = 'partial'
    FULL_OBJECT = 'full'

    def __init__(self, resource_class, type, id_field=None, relative_path=None, *args, **kwargs):
        """
        :param str type: One of 'uri', 'partial', 'full' depending on whether the resource is expanded or needs to
        be loaded separately.
        :param id_field: For types 'uri' and 'partial', specifies which field will be used as the nested resource id
        when constructing the URI.
        :param relative_path: The relative path (from this resource) to the nested resource. May contain {id} which
        will be replaced with the resource id. E.g. '/nested-resource/{id}/'
        """

        super(NestedResourceField, self).__init__(*args, **kwargs)

        if type in (self.URI_ONLY, self.PARTIAL_OBJECT) and not (id_field and relative_path):
            raise ValueError("Nested resources of type 'uri' or 'partial' must specify 'id_field' and 'relative_path'")

        self.resource_class = resource_class
        self.type = type
        self.id_field = id_field
        self.relative_path = relative_path

    def get_uri(self, obj, base_uri):
        if not base_uri.endswith('/') and not self.relative_path.startswith('/'):
            base_uri += '/'

        if self.type == self.URI_ONLY:
            resource_id = obj
        else:
            resource_id = obj.get(self.id_field)

        return ''.join((base_uri, self.relative_path.format(id=resource_id)))

    def to_python(self, value, resource):
        if self.type in (self.PARTIAL_OBJECT, self.FULL_OBJECT) and not isinstance(value, dict):
            raise ValueError(
                "Expected nested resource to be of type 'dict', got '{0}'".format(value.__class__.__name__)
            )
        elif self.type == self.URI_ONLY and not isinstance(value, six.string_types):
            raise ValueError(
                "Expected nested resource to be a string, got type {0}'".format(value.__class__.__name__)
            )

        if self.type == self.FULL_OBJECT:
            resource = self.resource_class()
            resource.populate_field_values(value)
            return resource
        else:
            return self.resource_class.get(self.get_uri(value, resource._url))

    def to_value(self, obj, resource):
        raise NotImplementedError('Serializing nested resources is not yet supported')


class ToOneField(NestedResourceField):
    """Same as NestedResourceField. Aliased for semantic reasons"""

    pass


class ToManyField(NestedResourceField):
    """To-many nested resource field"""

    def __iter__(self):
        """Implementing __iter__ avoids IDE inspection errors/warnings when this field is used in iteration"""

        while False:
            yield None

    def to_python(self, value, resource):
        if not isinstance(value, list):
            raise ValueError("Expected a list for 'to many' value, got '{0}'".format(value.__class__.__name__))

        return [super(ToManyField, self).to_python(x, resource) for x in value]

    def to_value(self, obj, resource):
        raise NotImplementedError('Serializing nested resources is not yet supported')