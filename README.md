# restle 0.5.1

[![Build Status](https://travis-ci.org/consbio/restle.png?branch=master)](https://travis-ci.org/consbio/restle)

Restle (pronounced like "wrestle") helps you create client interfaces for REST resources. If you've used the Django 
ORM or other relation mappers, the syntax should look familiar.

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
$ pip install restle
```

# Resources

The ```Resource``` class in restle performs the same function for web APIs as the ```Model``` class in Django does for 
databases (this is just an example; Django isn't required to use restle). It simplifies the task of mapping API 
responses to Python objects.

For example, suppose you have an API with responds to ```GET``` requests with the following.

```json
GET /api/messages/2389/

{
  "id": 2389,
  "sender": "Pi Pyson",
  "message": "Hello!",
  "read": false
}
```

In this case, the API has four fields: one integer, two text, and one boolean. The corresponding restle resource would
be.

```python
from restle.resources import Resource
from restle import fields

class MessageClient(Resource):
    id = fields.IntegerField()
    sender = fields.TextField()
    message = fields.TextField()
    read = fields.BooleanField()
```

Now that you have a resource, you can create start interacting with your web API.

```python
>>> c = MessageClient.get('http://example.com/api/messages/2389/')
>>> c.id
2389
>>> c.sender
'Pi Pyson'
>>> c.message
'Hello!'
>>> c.read
False
```

# Object lists and related resources

Okay, so retrieving a single message is great, but your API probably has a list view as well.

```json
GET /api/messages/

{
  "objects": [2389, 2374, 2489]
}
```

In this case, the list view just provides the ids. If you want the full messages, you'll need to make additional
requests for each message. You can use a ```ToManyField``` and restle will handle the rest for you.

```python
class MessageListClient(Resource):
    objects = fields.ToManyField(MessageClient, 'id', relative_path='{id}/'
```

The first argument to the ```ToManyField``` specifies the related resource class, the second argument tells restle that
the resource only returns a list of object *ids*, not the objects themselves, and the ```relative_path``` argument 
tells restle how to construct paths to the related resources. Now you can consume from the list view.

```python
>>> c = MessageListClient.get('http://example.com/api/messages/')
>>> len(c.objects)
3
>>> c.objects[0].message
'Hello!'
```

Alternatively, maybe the messages list view returns all the object data inline.

```json
GET /api/messages/

{
  "objects": [
    {
      "id": 2389,
      "sender": "Pi Pyson",
      "message": "Hello!",
      "read": false
    },
    {
      "id": 2374,
      ...
    },
    {
      "id": 2489,
      ...
    }
  ]
}
```

In this case, you only need to update your ```ToManyField``` definition to expect "full" objects.

```python
class MessageListClient(Resource):
    objects = fields.ToManyField(MessageClient, 'full')
```

The usage is exactly the same as for the id-only example. The last possible variation is partial objects:

```json
GET /api/messages/

{
  "objects": [
    {
      "id": 2389,
      "read": false
    },
    {
      "id": 2374,
      "read": false
    }
    {
      "id": 2489,
      "read": true
    }
  ]
}
```

In this case, the ```ToManyField``` definition should be updated to expect "partial" objects, and it will need to be 
told which field contains the id value.

```python
class MessageListClient(Resource):
    objects = fields.ToManyField(MessageClient, 'partial', id_field='id', relative_path='{id}/')
```

# Fuzzy key matching

Let's say you want your resource to use PEP8-compliant names, but the API provides you with camel case or some other
format. One solution to this is to pass in the ```name``` parameter for every field definition.

```python
    class SomeResource(Resource):
        some_field = fields.TextField(name='someField')
```

But you'd need to do that for every field name comprised of more than one word. An easier method is to use the
```match_fuzzy_keys``` option for the resource. This will convert both your field names and the keys from the API
to lower case and strip all non-alphanumeric characters before attempting to match them. This means you can take an
API output using the ```capWords``` convention:

```json
GET /api/some-resource/123/

{
    "ID": 123,
    "someField": "Some value",
    "someruntogetherfield": "No spaces!",
    "cRaZy-FoRmAt": "It's crazy!"
}
```

And use the standard ```snake_case``` convention for your resource field names.

```python
class SomeResource(Resource):
    id = fields.IntegerField()
    some_field = fields.TextField()
    some_run_together_field = fields.TextField()
    crazy_format = fields.TextField()

    class Meta:
        match_fuzzy_keys = True
```

```python
>>> c = SomeResource.get('http://example.com/api/some-resource/123/')
>>> c.id
123
>>> c.some_field
'Some value'
>>> c.some_run_together_field
'No spaces!'
>>> c.crazy_format
"It's crazy!"
```
