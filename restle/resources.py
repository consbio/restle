import logging
import six
from restle.exceptions import NotFoundException, HTTPException, MissingFieldException
from restle.options import ResourceOptions
from restle.utils import REQUEST_METHODS

logger = logging.getLogger(__name__)


class ResourceBase(type):
    """Resource metaclass"""

    def __new__(cls, name, bases, attrs):
        module = attrs.pop('__module__', None)
        new_class = super(ResourceBase, cls).__new__(cls, name, bases, {'__module__': module})
        meta = attrs.pop('Meta', None)
        new_class.add_to_class('_meta', ResourceOptions(meta))

        for name, value in attrs.items():
            new_class.add_to_class(name, value)

        return new_class

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
        self._strict = True

        self._populated_field_values = True if kwargs else False

        for field in self._meta.fields:
            if field._attr_name in kwargs:
                setattr(self, field._attr_name, kwargs.pop(field._attr_name))

        def action_wrapper(fn):
            def inner(*args, **kwargs):
                return fn(self, *args, **kwargs)
            return inner

        for action in self._meta.actions:
            setattr(self, action._attr_name, action_wrapper(action))

        if kwargs:
            raise TypeError('Resource received invalid keyword argument(s): {0}'.format(', '.join(kwargs.keys())))

    def _load_resource(self):
        """Load resource data from server"""

        url = '{0}://{1}{2}'.format(self._url_scheme, self._url_host, self._url_path)
        if self._url_params:
            url += '?{0}'.format(six.moves.urllib_parse.urlencode(self._url_params))

        r = REQUEST_METHODS[self._meta.get_method.lower()](url)

        if r.status_code == 404:
            raise NotFoundException('Server returned 404 Not Found for the URL {0}'.format(self._url_path))
        elif 200 > r.status_code >= 400:
            raise HTTPException('Server returned {0} ({1})'.format(r.status_code, r.reason))

        data = self._meta.serializer.to_dict(r.text)
        self.populate_field_values(data)

    def populate_field_values(self, data):
        """Load resource data and populate field values"""

        if not self._meta.case_sensitive_fields:
            data = {k.lower(): v for k, v in six.iteritems(data)}

        for field in self._meta.fields:
            name = field.name if self._meta.case_sensitive_fields else field.name.lower()
            value = None

            if name in data:
                value = field.to_python(data[name], self)
            elif field.required and field.default is None:
                message = "Response from {0} is missing required field '{1}'".format(self._url_path, field.name)
                if self._strict:
                    raise MissingFieldException(message)
                else:
                    logger.warn(message)
            elif field.default:
                value = field.default

            setattr(self, field._attr_name, value)

        self._populated_field_values = True

    def __getattr__(self, item):
        if self._populated_field_values:
            raise AttributeError("'{0}' object has no attribute '{1}'".format(self.__class__.__name__, item))

        self._load_resource()
        return getattr(self, item)

    @classmethod
    def get(cls, url, strict=True, lazy=True):
        self = cls()
        o = six.moves.urllib_parse.urlparse(url)

        self._url_scheme = 'https' if self._meta.force_https else o.scheme
        self._url_host = o.netloc
        self._url_path = o.path
        self._url_params = self._meta.get_parameters
        if o.query:
            self._url_params.update(six.moves.urllib_parse.parse_qs(o.query))

        self._strict = strict

        if not lazy:
            self._load_resource()

        return self