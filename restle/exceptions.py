import six


class ResourceException(Exception):
    pass


class NotFoundException(ResourceException):
    pass


class MissingFieldException(ResourceException):
    pass


class HTTPException(six.moves.http_client.HTTPException):
    def __init__(self, message, response=None):
        super(HTTPException, self).__init__(message)
        self.response = response
