# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import json

import pytest


@pytest.mark.parametrize(
    'http_method,http_path',
    (
        ('GET', '/api/v1/auth/clients'),
        ('POST', '/api/v1/auth/clients'),
    ),
)
def test_unauthorized_access(http_method, http_path, flask_app_client):
    response = flask_app_client.open(method=http_method, path=http_path)
    print(response)
    assert response.status_code == 401


def test_created_user_login(flask_app_client, admin_user, request):
    from app.modules.users.models import User

    with flask_app_client.login(admin_user, auth_scopes=('users:write',)):
        response = flask_app_client.post(
            '/api/v1/users/',
            content_type='application/json',
            data=json.dumps({'email': 'test.user@example.org', 'password': 'password'}),
        )
        assert response.status_code == 200
        assert response.json['email'] == 'test.user@example.org'
        assert response.json['is_active'] is True
        user_guid = response.json['guid']

    request.addfinalizer(lambda: User.query.get(user_guid).delete())

    response = flask_app_client.post(
        '/api/v1/auth/sessions',
        content_type='application/json',
        data=json.dumps({'email': 'test.user@example.org', 'password': 'password'}),
    )
    request.addfinalizer(lambda: flask_app_client.cookie_jar.clear())
    assert response.status_code == 200, response.json
    flask_app_client.cookie_jar.clear()

    # Check users can't login if is_active is False
    with flask_app_client.login(admin_user, auth_scopes=('users:write',)):
        response = flask_app_client.patch(
            f'/api/v1/users/{user_guid}',
            content_type='application/json',
            data=json.dumps(
                [
                    {
                        'op': 'test',
                        'path': '/current_password',
                        'value': admin_user.password_secret,
                    },
                    {
                        'op': 'replace',
                        'path': '/is_active',
                        'value': False,
                    },
                ],
            ),
        )
        assert response.status_code == 200
        assert response.json['is_active'] is False

    response = flask_app_client.post(
        '/api/v1/auth/sessions',
        content_type='application/json',
        data=json.dumps({'email': 'test.user@example.org', 'password': 'password'}),
    )
    assert response.status_code == 401, response.json
    assert response.json['message'] == 'Account Disabled'
