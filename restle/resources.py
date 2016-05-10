import logging
import string

import six
from requests import Session

from restle.exceptions import NotFoundException, HTTPException, MissingFieldException
from restle.options import ResourceOptions

logger = logging.getLogger(__name__)

ALPHANUMERIC = set(string.ascii_letters + string.digits)


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
        self._session = kwargs.pop('session', None)
        self._url = None
        self._params = None
        self._strict = True
        self._populated_field_values = True if kwargs else False

        if self._session is None:
            self._session = Session()

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

        url = self._url
        if self._params:
            url += '?{0}'.format(six.moves.urllib_parse.urlencode(self._params))

        r = getattr(self._session, self._meta.get_method.lower())(url)

        if r.status_code == 404:
            raise NotFoundException('Server returned 404 Not Found for the URL {0}'.format(self._url))
        elif not 200 <= r.status_code < 400:
            raise HTTPException('Server returned {0} ({1})'.format(r.status_code, r.reason), r)

        data = self._meta.deserializer.to_dict(r.text)
        self.populate_field_values(data)

    def populate_field_values(self, data):
        """Load resource data and populate field values"""

        if not self._meta.case_sensitive_fields:
            data = {k.lower(): v for k, v in six.iteritems(data)}

        if self._meta.match_fuzzy_keys:
            # String any non-alphanumeric chars from each key
            data = {''.join(x for x in k if x in ALPHANUMERIC).lower(): v for k, v in six.iteritems(data)}

        for field in self._meta.fields:
            name = field.name if self._meta.case_sensitive_fields else field.name.lower()
            value = None

            if self._meta.match_fuzzy_keys:
                name = ''.join(x for x in name if x in ALPHANUMERIC).lower()

            if name in data:
                value = field.to_python(data[name], self)
            elif field.required and field.default is None:
                message = "Response from {0} is missing required field '{1}'".format(self._url, field.name)
                if self._strict:
                    raise MissingFieldException(message)
                else:
                    logger.warn(message)
            elif field.default is not None:
                value = field.default

            setattr(self, field._attr_name, value)

        self._populated_field_values = True

    def __getattr__(self, item):
        if self._populated_field_values:
            raise AttributeError("'{0}' object has no attribute '{1}'".format(self.__class__.__name__, item))

        self._load_resource()
        return getattr(self, item)

    @classmethod
    def get(cls, url, strict=True, lazy=True, session=None):
        self = cls(session=session)
        o = six.moves.urllib_parse.urlparse(url)

        self._params = self._meta.get_parameters.copy()
        if o.query:
            query = six.moves.urllib_parse.parse_qs(o.query)
            self._params.update(
                {k: v[0] if v else '' for k, v in six.iteritems(query)}
            )

        self._url = '{0}://{1}{2}'.format('https' if self._meta.force_https else o.scheme, o.netloc, o.path)
        self._strict = strict

        if not lazy:
            self._load_resource()

        return self
