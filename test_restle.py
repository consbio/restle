import json

import httpretty
from mock import Mock
import pytest
import six
from requests import Session

from restle import fields
from restle.actions import Action
from restle.exceptions import HTTPException, MissingFieldException, NotFoundException
from restle.resources import Resource
from restle.serializers import JSONSerializer, URLSerializer


@pytest.fixture
def basic_action():
    return Action('action')


@pytest.fixture
def httpretty_activate(request):
    """Since fixtures don't work with decorators, this takes the place of the @httpretty.activate decorator"""

    httpretty.enable()

    def fin():
        httpretty.disable()

    request.addfinalizer(fin)


class TestActions(object):
    def test_constructor(self):
        Action('action')
        action = Action('action', required_params=['one', 'two'], optional_params=['three'])
        assert action.combined_params == set(['one', 'two', 'three'])

    def test_call(self, basic_action):
        resource = Mock(_url='http://example.com/my-resource', _session=None)

        basic_action.do_request = Mock()
        basic_action.process_response = Mock()

        basic_action(resource)  # Invoke Action.__call__()
        basic_action.do_request.assert_called_with(
            'http://example.com/my-resource/action', '', 'application/x-www-form-urlencoded', resource._session
        )

        with pytest.raises(ValueError) as e:
            basic_action(resource, foo='bar')
        assert 'unexpected keyword' in str(e)

        basic_action.required_params = set(['foo'])
        with pytest.raises(ValueError) as e:
            basic_action(resource)
        assert 'Missing required' in str(e)

    def test_contribute_to_class(self, basic_action):
        cls = Mock(_meta=Mock(actions=[]))
        basic_action.contribute_to_class(cls, 'action')
        assert cls._meta.actions == [basic_action]

    def test_get_uri(self, basic_action):
        base_uri = 'http://example.com/my-resource'
        uri = '{0}/action'.format(base_uri)

        assert basic_action.get_uri(base_uri) == uri
        assert basic_action.get_uri(base_uri + '/') == uri

    def test_prepare_params(self, basic_action):
        params = {'foo': 'bar'}
        params_as_json = '{"foo": "bar"}'
        params_as_url = 'foo=bar'
        json_content_type = 'application/json'
        form_content_type = 'application/x-www-form-urlencoded'

        basic_action.serializer = Mock(to_string=Mock(return_value=params_as_json), content_type=json_content_type)
        assert basic_action.prepare_params(params) == (params_as_json, json_content_type)

        basic_action._resource = Mock(_meta=Mock(serializer=basic_action.serializer))
        basic_action.serializer = None
        basic_action.params_via_post = True
        assert basic_action.prepare_params(params) == (params_as_json, json_content_type)

        basic_action.params_via_post = False
        assert basic_action.prepare_params(params) == (params_as_url, form_content_type)

    def test_do_request(self, basic_action, httpretty_activate):
        uri = 'http://example.com/my-resource/action'
        form_content_type = 'application/x-www-form-urlencoded'
        httpretty.register_uri(httpretty.POST, uri)

        basic_action.do_request(uri, 'foo=bar', '')
        assert httpretty.last_request().method == 'POST'
        assert httpretty.last_request().path.split('?', 1)[-1] == 'foo=bar'

        basic_action.params_via_post = True
        basic_action.do_request(uri, 'foo=bar', form_content_type)
        assert httpretty.last_request().method == 'POST'
        assert '?' not in httpretty.last_request().path
        assert httpretty.last_request().body.decode() == u'foo=bar'

    def test_do_request_with_session(self, basic_action, httpretty_activate):
        uri = 'http://example.com/my-resource/action'
        form_content_type = 'application/x-www-form-urlencoded'
        httpretty.register_uri(httpretty.POST, uri)

        session = Session()
        session.cookies['Foo'] = 'Bar'

        basic_action.do_request(uri, 'foo=bar', '', session=session)

        assert httpretty.last_request().headers['cookie'] == 'Foo=Bar'

    def test_process_response(self, basic_action):
        # Bad status
        response = Mock(status_code=500, reason='Server error')
        with pytest.raises(HTTPException):
            basic_action.process_response(response)

        # No response
        response = Mock(status_code=200, reason='Ok')
        assert basic_action.process_response(response) is None

        # Dict response
        basic_action.response_type = basic_action.DICT_RESPONSE
        basic_action.deserializer = JSONSerializer()
        response = Mock(status_code=200, reason='Ok', text='{"one": 1, "two": 2}')
        data = basic_action.process_response(response)
        assert data['one'] == 1
        assert data['two'] == 2

        # Aliases
        basic_action.response_aliases = {'one': 'neo', 'two': 'tow'}
        data = basic_action.process_response(response)
        assert data['neo'] == 1
        assert data['tow'] == 2

        # Object response
        basic_action.response_type = basic_action.OBJECT_RESPONSE
        obj = basic_action.process_response(response)
        assert obj.neo == 1
        assert obj.tow == 2


class TestResource(object):
    class BasicResource(Resource):
        name = fields.TextField()
        description = fields.TextField()
        optional = fields.TextField(required=False)
        default = fields.TextField(default='')

    class FuzzyResource(Resource):
        """ Resource class to test fuzzy key matching """

        snake_case = fields.TextField()
        camelCase = fields.TextField()
        CapWords = fields.TextField()
        runtogether = fields.TextField()
        ALL_CAPS = fields.TextField()

        class Meta:
            match_fuzzy_keys = True

    def test_options(self):
        class TestOptionsResource(Resource):
            class Meta:
                case_sensitive_fields = True
                match_fuzzy_keys = False
                force_https = False
                get_method = 'GET'
                get_parameters = {}
                deserializer = JSONSerializer()
                serializer = URLSerializer()

    def test_constructor(self):
        Resource()

        r = self.BasicResource(name='Foo', description='Bar')
        assert r.name == 'Foo'
        assert r.description == 'Bar'

    @httpretty.activate
    def test_load_resource(self):
        good_uri = 'http://example.com/my-resource'
        bad_uri = 'http://example.com/not-there'
        httpretty.register_uri(httpretty.GET, good_uri, body='{}')
        httpretty.register_uri(httpretty.GET, bad_uri, status=404)

        r = self.BasicResource.get(good_uri)
        r.populate_field_values = Mock()
        r._load_resource()
        assert httpretty.last_request().method == 'GET'
        assert r.populate_field_values.called

        r = self.BasicResource.get(bad_uri)
        with pytest.raises(NotFoundException):
            r._load_resource()

    def test_populate_field_values(self):
        # All fields provided
        r = self.BasicResource()
        r.populate_field_values({'name': 'Foo', 'description': 'Bar', 'optional': 'Maybe'})
        assert r._populated_field_values
        assert r.name == 'Foo'
        assert r.description == 'Bar'
        assert r.optional == 'Maybe'

        # Optional field excluded
        r = self.BasicResource()
        r.populate_field_values({'name': 'Foo', 'description': 'Bar'})
        assert r._populated_field_values
        assert r.name == 'Foo'
        assert r.description == 'Bar'
        assert r.optional is None

        # Required field excluded
        r = self.BasicResource()
        with pytest.raises(MissingFieldException):
            r.populate_field_values({'name': 'Foo'})

        # Required field excluded, strict=False
        r = self.BasicResource.get('http://example.com/my-resource', strict=False)
        r.populate_field_values({'name': 'Foo'})
        assert r._populated_field_values
        assert r.name == 'Foo'
        assert r.description is None
        assert r.optional is None

        # Test false-y default value
        assert r.default == ''

    def test_fuzzy_keys(self):
        r = self.FuzzyResource()
        r.populate_field_values({
            'snakeCase': 'snake case value',
            'camel-case': 'camel case value',
            'cap_words': 'cap words value',
            'run-together': 'runtogether value',
            'allcaps': 'all caps value'
        })

        assert r.snake_case == 'snake case value'
        assert r.camelCase == 'camel case value'
        assert r.CapWords == 'cap words value'
        assert r.runtogether == 'runtogether value'
        assert r.ALL_CAPS == 'all caps value'

    def test_get(self):
        r = self.BasicResource.get('http://example.com/my-resource')
        assert isinstance(r, self.BasicResource)

    def test_get_with_session(self, httpretty_activate):
        uri = 'http://example.com/my-resource/'
        httpretty.register_uri(httpretty.GET, uri, body='{}', content_type='application/json')

        session = Session()
        session.cookies['Foo'] = 'Bar'
        r = self.BasicResource.get('http://example.com/my-resource/', session=session, lazy=False, strict=False)

        assert httpretty.last_request().headers['cookie'] == 'Foo=Bar'

    def test_field_inheritance(self):
        """ Makes sure fields from a parent class are properly inherited by the subclasses """

        class SuperResource(Resource):
            name = fields.TextField()
            version = fields.TextField()

        class OtherSuperResource(Resource):
            tags = fields.ListField()

        class SubResource(SuperResource):
            description = fields.TextField()
            version = fields.NumberField()

        class MultipleSubResource(SuperResource, OtherSuperResource):
            description = fields.TextField()
            version = fields.NumberField(required=False)

        r = SubResource()
        r.populate_field_values({'name': 'Foo', 'description': 'Bar', 'version': '2'})

        assert r.name == 'Foo'
        assert r.description == 'Bar'
        assert r.version == 2

        r = MultipleSubResource()
        r.populate_field_values({'name': 'Foo', 'description': 'Bar', 'tags': ['foo', 'bar']})

        assert r.name == 'Foo'
        assert r.description == 'Bar'
        assert r.tags == ['foo', 'bar']


class TestFields(object):
    """Test various Field classes"""

    def test_contribute_to_class(self):
        f = fields.Field()
        cls = Mock(_meta=Mock(fields=[]))
        f.contribute_to_class(cls, 'field')
        assert f.name == 'field'
        assert cls._meta.fields == [f]

    def test_list_field(self):
        f = fields.ListField()
        assert f.to_python(['one', 'two'], None) == ['one', 'two']

        with pytest.raises(ValueError):
            f.to_python({'one': 'two'}, None)

        with pytest.raises(ValueError):
            f.to_python('foo', None)

    def test_text_field(self):
        f = fields.TextField()
        assert isinstance(f.to_python(six.text_type('Foo'), None), six.text_type)
        if six.PY3:
            assert isinstance(f.to_python(b'Foo', None), str)
        else:
            assert isinstance(f.to_python('Foo', None), six.text_type)

        f = fields.TextField(encoding=None)
        assert f.to_python(None, None) is None
        assert isinstance(f.to_python(six.text_type('Foo'), None), six.text_type)
        if six.PY3:
            assert isinstance(f.to_python(b'Foo', None), six.binary_type)
        else:
            assert isinstance(f.to_python('Foo', None), six.binary_type)

        f = fields.TextField()
        assert f.to_python(' Foo\t', None) == ' Foo\t'

        f = fields.TextField(strip=True)
        assert f.to_python(' Foo\t', None) == 'Foo'

        f = fields.TextField(lower=True)
        assert f.to_python(' Foo\t', None) == ' foo\t'

        f = fields.TextField(strip=True, lower=True)
        assert f.to_python(' Foo\t', None) == 'foo'

    def test_boolean_field(self):
        f = fields.BooleanField()
        assert f.to_python(None, None) is None
        assert isinstance(f.to_python(1, None), bool)
        assert f.to_python(1, None) is True
        assert f.to_python(0, None) is False
        assert f.to_python('true', None) is True
        assert f.to_python('false', None) is True
        assert f.to_python('', None) is False

    def test_number_field(self):
        f = fields.NumberField()
        assert f.to_python(None, None) is None
        assert isinstance(f.to_python(1, None), int)
        assert isinstance(f.to_python(1.1, None), float)
        assert isinstance(f.to_python('1', None), int)
        assert isinstance(f.to_python('1.1', None), float)

    def test_integer_field(self):
        f = fields.IntegerField()
        assert f.to_python(None, None) is None
        assert isinstance(f.to_python(1.0, None), int)
        assert f.to_python(1.1, None) == 1
        assert isinstance(f.to_value(1.0, None), int)

    def test_float_field(self):
        f = fields.FloatField()
        assert f.to_python(None, None) is None
        assert isinstance(f.to_python(1, None), float)
        assert f.to_python('1.1', None) == 1.1
        assert isinstance(f.to_value(1, None), float)

    def test_object_field(self):
        data = {
            'li': [{'foo': 'bar'}, 2, 3],
            'this': 5
        }
        f = fields.ObjectField(aliases={'this': 'that'})
        assert f.to_python(None, None) is None
        obj = f.to_python(data, None)
        assert obj.li[0].foo == 'bar'
        assert obj.that == 5
        assert f.to_value(obj, None) == data

    def test_nested_field(self):
        data = {
            'foo': 'bar',
            'id': 2
        }
        f = fields.NestedResourceField(Mock(), fields.NestedResourceField.FULL_OBJECT, relative_path='{id}/')
        obj = f.to_python(data, Mock(_url='http://example.com/api/resource/'))
        assert obj._url == 'http://example.com/api/resource/2/'


class TestExamples(object):
    """Make sure examples given in the documentation actually work"""

    def test_simple(self, httpretty_activate):
        """Test simple example given in the README intro"""

        uri = 'http://example.com/some-resource'
        httpretty.register_uri(
            httpretty.GET, uri, body='{"version": 1.2, "name": "Some API"}', content_type='application/json'
        )

        class SomeClient(Resource):
            version = fields.TextField()
            name = fields.TextField()
            description = fields.TextField(required=False)

        c = SomeClient.get(uri)
        assert c.version == "1.2"
        assert c.name == "Some API"
        assert c.description is None

    def test_message_client(self, httpretty_activate):
        """Tests the `MessageClient` example in the README"""

        uri = 'http://example.com/api/messages/2389/'
        data = json.dumps({
            'id': 2389,
            'sender': 'Pi Pyson',
            'message': 'Hello!',
            'read': False
        })
        httpretty.register_uri(httpretty.GET, uri, body=data)

        class MessageClient(Resource):
            id = fields.IntegerField()
            sender = fields.TextField()
            message = fields.TextField()
            read = fields.BooleanField()

        c = MessageClient.get('http://example.com/api/messages/2389/')
        assert c.id == 2389
        assert c.sender == 'Pi Pyson'
        assert c.message == 'Hello!'
        assert c.read is False
        
    def test_message_list_client_with_uid(self, httpretty_activate):
        """Tests the `MessageListClient` example, using 'uid' relation type"""

        messages = (('http://example.com/api/messages/{id}/'.format(id=message_id), json.dumps({
            'id': message_id,
            'sender': 'Pi Pyson',
            'message': 'Hello!',
            'read': read
        })) for message_id, read in ((2389, False), (2374, False), (2489, True)))
        for uri, data in messages:
            httpretty.register_uri(httpretty.GET, uri, body=data)

        uri = 'http://example.com/api/messages/'
        data = json.dumps({'objects': [2389, 2374, 2489]})
        httpretty.register_uri(httpretty.GET, uri, body=data)

        class MessageClient(Resource):
            id = fields.IntegerField()
            sender = fields.TextField()
            message = fields.TextField()
            read = fields.BooleanField()

        class MessageListClient(Resource):
            objects = fields.ToManyField(MessageClient, 'id', relative_path='{id}/')

        c = MessageListClient.get('http://example.com/api/messages/')
        assert len(c.objects) == 3
        assert c.objects[0].message == 'Hello!'
        assert c.objects[0].id == 2389
        assert c.objects[0].read is False
        assert c.objects[1].id == 2374
        assert c.objects[1].read is False
        assert c.objects[2].id == 2489
        assert c.objects[2].read is True

    def test_message_list_client_with_full(self, httpretty_activate):
        """Tests the `MessageListClient` example, using 'full' relation type"""

        uri = 'http://example.com/api/messages/'
        data = json.dumps({
            'objects': [{
                'id': message_id,
                'sender': 'Pi Pyson',
                'message': 'Hello!',
                'read': read
            } for message_id, read in ((2389, False), (2374, False), (2489, True))]
        })
        httpretty.register_uri(httpretty.GET, uri, body=data)

        class MessageClient(Resource):
            id = fields.IntegerField()
            sender = fields.TextField()
            message = fields.TextField()
            read = fields.BooleanField()

        class MessageListClient(Resource):
            objects = fields.ToManyField(MessageClient, 'full')

        c = MessageListClient.get('http://example.com/api/messages/')
        assert len(c.objects) == 3
        assert c.objects[0].message == 'Hello!'
        assert c.objects[0].id == 2389
        assert c.objects[0].read is False
        assert c.objects[1].id == 2374
        assert c.objects[1].read is False
        assert c.objects[2].id == 2489
        assert c.objects[2].read is True

    def test_message_list_client_with_partial(self, httpretty_activate):
        """Tests the `MessageListClient` example, using 'partial' relation type"""

        messages = (('http://example.com/api/messages/{id}/'.format(id=message_id), json.dumps({
            'id': message_id,
            'sender': 'Pi Pyson',
            'message': 'Hello!',
            'read': read
        })) for message_id, read in ((2389, False), (2374, False), (2489, True)))
        for uri, data in messages:
            httpretty.register_uri(httpretty.GET, uri, body=data)

        uri = 'http://example.com/api/messages/'
        data = json.dumps({
            'objects': [{
                'id': message_id,
                'read': read
            } for message_id, read in ((2389, False), (2374, False), (2489, True))]
        })
        httpretty.register_uri(httpretty.GET, uri, body=data)

        class MessageClient(Resource):
            id = fields.IntegerField()
            sender = fields.TextField()
            message = fields.TextField()
            read = fields.BooleanField()

        class MessageListClient(Resource):
            objects = fields.ToManyField(MessageClient, 'partial', id_field='id', relative_path='{id}/')

        c = MessageListClient.get('http://example.com/api/messages/')
        assert len(c.objects) == 3
        assert c.objects[0].message == 'Hello!'
        assert c.objects[0].id == 2389
        assert c.objects[0].read is False
        assert c.objects[1].id == 2374
        assert c.objects[1].read is False
        assert c.objects[2].id == 2489
        assert c.objects[2].read is True

    def test_fuzzy_key_matching(self, httpretty_activate):
        """ Tests the fuzzy key matching example """

        httpretty.register_uri(httpretty.GET, 'http://example.com/api/some-resource/123/', body=json.dumps({
            "ID": 123,
            "someField": "Some value",
            "someruntogetherfield": "No spaces!",
            "cRaZy-FoRmAt": "It's crazy!"
        }))

        class SomeResource(Resource):
            id = fields.IntegerField()
            some_field = fields.TextField()
            some_run_together_field = fields.TextField()
            crazy_format = fields.TextField()

            class Meta:
                match_fuzzy_keys = True

        c = SomeResource.get('http://example.com/api/some-resource/123/')
        assert c.id == 123
        assert c.some_field == 'Some value'
        assert c.some_run_together_field == 'No spaces!'
        assert c.crazy_format == "It's crazy!"
