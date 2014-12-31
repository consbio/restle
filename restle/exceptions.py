import six


class ResourceException(Exception):
    pass


class NotFoundException(ResourceException):
    pass


class MissingFieldException(ResourceException):
    pass


HTTPException = six.moves.http_client.HTTPException