import six
from restle.options import ResourceOptions


class ResourceBase(type):
    """Resource metaclass"""

    def __new__(cls, name, bases, attrs):
        new_class = super(ResourceBase, cls).__new__(cls, name, bases, attrs)
        meta = attrs.pop('Meta', None)
        new_class.add_to_class('_meta', ResourceOptions(meta))

        for name, value in attrs.items():
            new_class.add_to_class(name, value)

    def add_to_class(cls, name, value):
        if hasattr(value, 'contribute_to_class'):
            value.contribute_to_class(cls, name)
        else:
            setattr(cls, name, value)


class Resource(six.with_metaclass(ResourceBase)):
    def __init__(self, **kwargs):
        self._url_scheme = None
        self._url_host = None
        self._url_path = None
        self._url_params = None

        self._populated_field_values = False

        for field in self._meta.fields:
            if field.name in kwargs:
                setattr(self, field.name, kwargs.pop(field.name))

        if kwargs:
            raise TypeError('Resource received invalid keyword argument(s): {0}'.format(', '.join(kwargs.keys())))

    def _populate_field_values(self):
        """Load resource data and populate field values"""

        # Todo
        self._populated_field_values = True

    def __getattr__(self, item):
        if self._populated_field_values:
            raise AttributeError("'{0}' object has no attribute '{1}'".format(self.__class__.__name__, item))

        self._populate_field_values()
        return getattr(self, item)

    @classmethod
    def get(cls, url):
        self = cls()
        o = six.moves.urllib_parse.urlparse(url)
        self._url_scheme = 'https' if self._meta.force_https else o.scheme
        self._url_host = o.netloc
        self._url_path = o.path
        self._url_params = six.moves.urllib_parse.parse_qs(o.query)

        return self