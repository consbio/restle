def get_response_encoding(response, default='utf-8'):
    encoding = default
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
    return encoding