import json


class JSONSerializer(object):
    @staticmethod
    def to_dict(s):
        return json.loads(s, strict=False)

    @staticmethod
    def to_string(d):
        return json.dumps(d)