from restle.serializers import JSONSerializer

OPTION_NAMES = ('force_https', 'serializer',)  # Todo: overridalbe options here


class ResourceOptions(object):
    def __init__(self, meta):
        self.force_https = False
        self.serializer = JSONSerializer()

        self.fields = []
        self.meta = meta

    def contribute_to_class(self, cls, name):
        cls._meta = self

        if self.meta:
            meta_attrs = self.meta.__dict__.copy()
            for name in OPTION_NAMES:
                if name in meta_attrs:
                    setattr(self, name, meta_attrs.pop(name))

            # Check for invalid attributes
            if meta_attrs:
                raise TypeError('Meta class contains invalid attribute(s): {0}'.format(', '.join(meta_attrs.keys())))

            del self.meta