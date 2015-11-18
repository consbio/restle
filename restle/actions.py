import six
from requests import Session

from restle.exceptions import HTTPException
from restle.serializers import URLSerializer


class Action(object):
    """Action base class"""

    NO_RESPONSE = 'none'
    DICT_RESPONSE = 'dict'
    OBJECT_RESPONSE = 'object'

    def __init__(self, relative_path, **kwargs):
        self.relative_path = relative_path
        self.http_method = kwargs.pop('http_method', 'POST')
        self.expected_http_codes = set(kwargs.pop('expected_http_code', six.moves.xrange(200, 300)))
        self.required_params = set(kwargs.pop('required_params', []))
        self.optional_params = set(kwargs.pop('optional_params', []))
        self.param_defaults = kwargs.pop('param_defaults', {})
        self.param_aliases = kwargs.pop('param_aliases', {})
        self.params_via_post = kwargs.pop('params_via_post', False)
        self.response_type = kwargs.pop('response_type', 'none')
        self.response_class = kwargs.pop('response_class', None)
        self.response_aliases = kwargs.pop('response_aliases', {})
        self.serializer = kwargs.pop('serializer', None)
        self.deserializer = kwargs.pop('deserializer', None)

        self.combined_params = self.optional_params.union(self.required_params)

        if kwargs:
            raise ValueError("Got unexpected keyword argument(s): '{0}'".format(', '.join(kwargs.keys())))

    def __call__(self, resource, **kwargs):
        invalid_kwargs = set(six.iterkeys(kwargs)).difference(self.combined_params)
        if invalid_kwargs:
            raise ValueError("Got unexpected keyword argument(s): '{0}'".format(', '.join(invalid_kwargs)))

        params = self.param_defaults.copy()
        params.update(kwargs)

        missing_required_params = self.required_params.difference(set(six.iterkeys(params)))
        if missing_required_params:
            raise ValueError("Missing required parameter(s): '{0}'".format(', '.join(missing_required_params)))

        params, content_type = self.prepare_params({self.param_aliases.get(k, k): v for k, v in six.iteritems(params)})
        return self.process_response(
            self.do_request(self.get_uri(resource._url), params, content_type, resource._session)
        )

    def contribute_to_class(self, cls, name):
        self._attr_name = name
        self._resource = cls

        cls._meta.actions.append(self)

    def get_uri(self, base_uri):
        if not base_uri.endswith('/') and not self.relative_path.startswith('/'):
            base_uri += '/'

        return ''.join((base_uri, self.relative_path))

    def prepare_params(self, params):
        if self.serializer:
            serializer = self.serializer
        elif self.params_via_post and self.http_method in ('POST', 'PUT', 'PATCH'):
            serializer = self._resource._meta.serializer
        else:
            serializer = URLSerializer

        return serializer.to_string(params), serializer.content_type

    def do_request(self, url, params, content_type, session=None):
        body = None
        headers = None
        if params and not self.params_via_post:
            url += '?{0}'.format(params)
        elif self.params_via_post:
            body = params
            headers = {'Content-type': content_type}

        if session is None:
            session = Session()

        return getattr(session, self.http_method.lower())(url, data=body, headers=headers)

    def process_response(self, response):
        if response.status_code not in self.expected_http_codes:
            raise HTTPException(
                'Received unexpected response from server: {0} ({1})'.format(response.status_code, response.reason)
            )

        if self.response_type == self.NO_RESPONSE:
            return

        data = (self.deserializer or self._resource._meta.serializer).to_dict(response.text)

        def alias_keys(d):
            if isinstance(d, dict):
                return {self.response_aliases.get(k, k): alias_keys(v) for k, v in six.iteritems(d)}
            elif isinstance(d, list):
                return [alias_keys(x) for x in d]
            return d

        data = alias_keys(data)

        if self.response_type == self.OBJECT_RESPONSE:
            if self.response_class:
                return self.response_class(data)
            else:
                def convert_to_class(d):
                    if isinstance(d, dict):
                        return type('AnonymousObject', (), {k: convert_to_class(v) for k, v in six.iteritems(d)})
                    elif isinstance(d, list):
                        return [convert_to_class(x) for x in d]
                    return d

                return convert_to_class(data)
        return data
