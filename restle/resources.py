import logging
import six
from restle.exceptions import NotFoundException, HTTPException, MissingFieldException
from restle.options import ResourceOptions

logger = logging.getLogger(__name__)


class ResourceBase(type):
    """Resource metaclass"""

    def __new__(cls, name, bases, attrs):
        module = attrs.pop('__module__')
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

        self._populated_field_values = False

        for field in self._meta.fields:
            if field._attr_name in kwargs:
                setattr(self, field._attr_name, kwargs.pop(field._attr_name))

        if kwargs:
            raise TypeError('Resource received invalid keyword argument(s): {0}'.format(', '.join(kwargs.keys())))

    def _populate_field_values(self):
        """Load resource data and populate field values"""

        if self._url_scheme == 'https':
            conn = six.moves.http_client.HTTPSConnection(self._url_host)
        else:
            conn = six.moves.http_client.HTTPConnection(self._url_host)

        path = self._url_path
        if self._url_params:
            path += '?{0}'.format(six.moves.urllib_parse.urlencode(self._url_params))

        conn.request(self._meta.get_method, path)
        response = conn.getresponse()

        if response.status == 404:
            raise NotFoundException('Server returned 404 Not Found for the URL {0}'.format(self._url_path))
        elif 200 > response.status >= 400:
            raise HTTPException('Server returned {0} ({1})'.format(response.status, response.reason))

        raw_data = response.read()

        # Determine encoding
        encoding = 'utf-8'
        content_type = response.getheader('content-type')
        if content_type:
            content_type_parameters = content_type.split(';')[1:]
            for parameter in content_type_parameters:
                if '=' in parameter:
                    name, value = parameter.split('=', 1)
                else:
                    name = parameter
                    value = None

                if name.lower() == 'charset':
                    encoding = value
        raw_data = raw_data.decode(encoding)

        data = self._meta.serializer.to_dict(raw_data)
        if not self._meta.case_sensitive_fields:
            data = {k.lower(): v for k, v in six.iteritems(data)}

        for field in self._meta.fields:
            name = field.name if self._meta.case_sensitive_fields else field.name.lower()
            value = None

            if name in data:
                value = field.to_python(data[name])
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

        self._populate_field_values()
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
            self._populate_field_values()

        return self