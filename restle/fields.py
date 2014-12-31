import six


class Field(object):
    """Field base class"""

    def __init__(self, name=None, required=True, default=None):
        self.name = name
        self.required = True
        self.default = None

    def contribute_to_class(self, cls, name):
        if not self.name:
            self.name = name

        cls._meta.fields.append(self)

    def to_python(self, value):
        """Returns the value as returned by the serializer converted to a Python object"""

        return value

    def to_value(self, obj):
        """Returns the Python object converted to a value ready for serialization"""

        raise NotImplementedError("Can't serialize base Field class")


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

    def to_value(self, obj):
        return obj