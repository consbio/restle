import json
import six


class JSONSerializer(object):
    content_type = 'application/json'

    @staticmethod
    def to_dict(s):
        return json.loads(s, strict=False)

    @staticmethod
    def to_string(d):
        return json.dumps(d)


class URLSerializer(object):
    content_type = 'application/x-www-form-urlencoded'

    @staticmethod
    def to_dict(s):
        return six.moves.urllib_parse.parse_qs(s)

    @staticmethod
    def to_string(d):
        return six.moves.urllib_parse.urlencode(d)