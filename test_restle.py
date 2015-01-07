import httpretty
from mock import Mock
import pytest
from restle.actions import Action


@pytest.fixture
def basic_action():
    return Action('action')


def test_action_constructor(basic_action):
    Action('action')
    action = Action('action', required_params=['one', 'two'], optional_params=['three'])
    assert action.combined_params == set(['one', 'two', 'three'])


def test_action_call(basic_action):
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


def test_action_contribute_to_class(basic_action):
    cls = Mock(_meta=Mock(actions=[]))
    basic_action.contribute_to_class(cls, 'action')
    assert cls._meta.actions == [basic_action]


def test_action_get_uri(basic_action):
    base_uri = 'http://example.com/my-resource'
    uri = '{0}/action'.format(base_uri)

    assert basic_action.get_uri(base_uri) == uri
    assert basic_action.get_uri(base_uri + '/') == uri


def test_action_prepare_params(basic_action):
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


@httpretty.activate
def test_action_do_request(basic_action):
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


def test_action_process_response(basic_action):
    pass  # Todo