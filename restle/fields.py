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

    def to_python(self, value):
        """Returns the value as returned by the serializer converted to a Python object"""

        return value

    def to_value(self, obj):
        """Returns the Python object converted to a value ready for serialization"""

        return obj


class DictField(Field):
    """Same as base field. Aliased for semantic purposes."""

    pass


class TextField(Field):
    def __init__(self, encoding='utf-8', *args, **kwargs):
        super(TextField, self).__init__(*args, **kwargs)

        self.encoding = encoding

    def to_python(self, value):
        """Converts to unicode if self.encoding != None, otherwise returns input without attempting to decode"""

        if isinstance(value, six.text_type):
            return value

        if self.encoding is None and isinstance(value, six.string_types):
            return value

        if self.encoding is not None and isinstance(value, six.binary_type):
            return value.decode(self.encoding)

        return six.text_type(value)


class BooleanField(Field):
    def to_python(self, value):
        return bool(value)


class NumberField(Field):
    def to_python(self, value):
        if isinstance(value, (int, float)):
            return value

        number = float(value)
        return int(number) if number.is_integer() else number


class IntegerField(NumberField):
    def to_python(self, value):
        return int(super(IntegerField, self).to_python(value))

    def to_value(self, obj):
        return int(obj)


class FloatField(NumberField):
    def to_python(self, value):
        return float(super(FloatField, self).to_python(value))

    def to_value(self, obj):
        return float(obj)


class ObjectField(Field):
    """Represents a dictionary as a Python object (lists, too)"""

    def __init__(self, class_name='AnonymousObject', aliases={}, *args, **kwargs):
        self.class_name = class_name
        self.aliases = aliases
        self.reverse_aliases = {v: k for k, v in six.iteritems(aliases)}

        super(ObjectField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        """Dictionary to Python object"""

        if isinstance(value, dict):
            d = {
                self.aliases.get(k, k): self.to_python(v) if isinstance(v, (dict, list)) else v
                for k, v in six.iteritems(value)
            }
            return type(self.class_name, (), d)
        elif isinstance(value, list):
            return [self.to_python(x) if isinstance(x, (dict, list)) else x for x in value]
        else:
            return value

    def to_value(self, obj, visited=set()):
        """Python object to dictionary"""

        if id(obj) in visited:
            raise ValueError('Circular reference detected when attempting to serialize object')


        if isinstance(obj, (list, tuple, set)):
            return [self.to_value(x) if hasattr(x, '__dict__') else x for x in obj]
        elif hasattr(obj, '__dict__'):
            attrs = obj.__dict__.copy()
            for key in six.iterkeys(obj.__dict__):
                if key.startswith('_'):
                    del attrs[key]

            return {
                self.reverse_aliases.get(k, k): self.to_value(v) if hasattr(v, '__dict__') else v
                for k, v in six.iteritems(attrs)
            }
        else:
            return obj