import six


class Field(object):
    """Field base class"""

    def __init__(self, name=None, required=True, default=None):
        self._attr_name = None

        self.name = name
        self.required = required
        self.default = default

    def contribute_to_class(self, cls, name):
        self._attr_name = name

        if not self.name:
            self.name = name

        cls._meta.fields.append(self)

    def to_python(self, value):
        """Returns the value as returned by the serializer converted to a Python object"""

        return value

    def to_value(self, obj):
        """Returns the Python object converted to a value ready for serialization"""

        return obj


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