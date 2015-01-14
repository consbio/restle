# restle 0.1.0

[![Build Status](https://travis-ci.org/consbio/restle.png?branch=master)](https://travis-ci.org/consbio/restle)

Restle (pronounced like "wrestle") helps you create client interfaces for REST resources. If you've used the Django 
ORM or other relation mappers, the syntax should look familiar:

```python
from restle.resources import Resource
from restle import fields


class SomeClient(Resource):
    version = fields.TextField()
    name = fields.TextField()
    description = fields.TextField(required=False)
    

c = SomeClient.get('http://example.com/some-resource')
print(c.version)
print(c.name)
print(c.description)
```

# Install

```bash
$ pip install https://github.com/consbio/restle/archive/0.1.0.tar.gz
```