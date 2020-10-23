# -*- coding: utf-8 -*-
import pytest
import uuid
import six


@pytest.mark.parametrize(
    'auth_scopes,redirect_uris',
    (
        (['auth:write'], ['http://1', 'http://2']),
        (['auth:write', 'auth:read'], None),
    ),
)
def test_creating_oauth2_client(
    flask_app_client, regular_user, db, auth_scopes, redirect_uris
):
    with flask_app_client.login(regular_user, auth_scopes=auth_scopes):
        response = flask_app_client.post(
            '/api/v1/auth/clients',
            data={
                'redirect_uris': redirect_uris,
                'default_scopes': ['users:read', 'users:write', 'auth:read'],
            },
        )

    assert response.status_code == 200
    assert response.content_type == 'application/json'
    assert isinstance(response.json, dict)
    assert set(response.json.keys()) >= {
        'user_guid',
        'guid',
        'secret',
        'level',
        'default_scopes',
        'redirect_uris',
    }
    client_guid = uuid.UUID(response.json['guid'])
    assert isinstance(client_guid, uuid.UUID)
    assert isinstance(response.json['secret'], six.text_type)
    assert isinstance(response.json['default_scopes'], list)
    assert set(response.json['default_scopes']) == {
        'users:read',
        'users:write',
        'auth:read',
    }
    assert isinstance(response.json['redirect_uris'], list)

    # Cleanup
    from app.modules.auth.models import OAuth2Client

    oauth2_client_instance = OAuth2Client.query.get(client_guid)
    assert oauth2_client_instance.secret == response.json['secret']

    with db.session.begin():
        db.session.delete(oauth2_client_instance)


@pytest.mark.parametrize(
    'auth_scopes',
    (
        [],
        ['auth:read'],
        ['auth:read', 'user:read'],
        ['user:read'],
    ),
)
def test_creating_oauth2_client_by_unauthorized_user_must_fail(
    flask_app_client, regular_user, auth_scopes
):
    with flask_app_client.login(regular_user, auth_scopes=auth_scopes):
        response = flask_app_client.post(
            '/api/v1/auth/clients',
            data={'default_scopes': ['users:read', 'users:write', 'invalid']},
        )

    assert response.status_code == 401
    assert response.content_type == 'application/json'
    assert set(response.json.keys()) >= {'status', 'message'}


def test_creating_oauth2_client_must_fail_for_invalid_scopes(
    flask_app_client, regular_user
):
    with flask_app_client.login(regular_user, auth_scopes=['auth:write']):
        response = flask_app_client.post(
            '/api/v1/auth/clients',
            data={
                'redirect_uris': [],
                'default_scopes': ['users:read', 'users:write', 'invalid'],
            },
        )

    assert response.status_code == 422
    assert response.content_type == 'application/json'
    assert set(response.json.keys()) >= {'status', 'message'}
