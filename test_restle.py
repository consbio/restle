import httpretty
from mock import Mock
import pytest
from restle import fields
from restle.actions import Action
from restle.exceptions import HTTPException, MissingFieldException
from restle.resources import Resource
from restle.serializers import JSONSerializer


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
        resource = Mock(_url_scheme='http', _url_host='example.com', _url_path='/my-resource')

        basic_action.do_request = Mock()
        basic_action.process_response = Mock()

        basic_action(resource)  # Invoke Action.__call__()
        basic_action.do_request.assert_called_with(
            'http://example.com/my-resource/action', '', 'application/x-www-form-urlencoded'
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

    def test_constructor(self):
        Resource()

        r = self.BasicResource(name='Foo', description='Bar')
        assert r.name == 'Foo'
        assert r.description == 'Bar'

    @httpretty.activate
    def test_load_resource(self):
        uri = 'http://example.com/my-resource'
        httpretty.register_uri(httpretty.GET, uri, body='{}')

        r = self.BasicResource.get(uri)
        r.populate_field_values = Mock()
        r._load_resource()

        assert httpretty.last_request().method == 'GET'
        assert r.populate_field_values.called

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

    def test_get(self):
        r = self.BasicResource.get('http://example.com/my-resource')
        assert isinstance(r, self.BasicResource)


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