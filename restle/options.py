from restle.serializers import JSONSerializer, URLSerializer

OPTION_NAMES = (
    'case_sensitive_fields', 'match_fuzzy_keys', 'force_https', 'get_method', 'get_parameters', 'deserializer',
    'serializer'
)


class ResourceOptions(object):
    def __init__(self, meta):
        self.case_sensitive_fields = True
        self.match_fuzzy_keys = False
        self.force_https = False
        self.get_method = 'GET'
        self.get_parameters = {}
        self.deserializer = JSONSerializer()
        self.serializer = URLSerializer()

        self.fields = []
        self.actions = []
        self.meta = meta

    def contribute_to_class(self, cls, name):
        cls._meta = self

        if self.meta:
            meta_attrs = self.meta.__dict__.copy()

            # Remove private attributes
            for key in self.meta.__dict__:
                if key.startswith('_'):
                    del meta_attrs[key]

            for name in OPTION_NAMES:
                if name in meta_attrs:
                    setattr(self, name, meta_attrs.pop(name))

            # Check for invalid attributes
            if meta_attrs:
                raise TypeError('Meta class contains invalid attribute(s): {0}'.format(', '.join(meta_attrs.keys())))

            del self.meta
