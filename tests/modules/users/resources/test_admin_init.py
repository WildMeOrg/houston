# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import json
from app.modules.users.models import User


def test_admin_creation(flask_app_client):
    response = flask_app_client.get('/api/v1/users/admin_user_initialized')
    assert response.status_code == 200
    assert not response.json['initialized']  # False cuz we have no admin

    # fails due to bad email address
    data = json.dumps({'email': 'fail', 'password': 'test1234'})
    response = flask_app_client.post(
        '/api/v1/users/admin_user_initialized', content_type='application/json', data=data
    )
    assert response.status_code == 422

    # create one
    valid_email = 'test-admin@example.com'
    data = json.dumps({'email': valid_email, 'password': 'test1234'})
    response = flask_app_client.post(
        '/api/v1/users/admin_user_initialized', content_type='application/json', data=data
    )
    assert response.status_code == 200
    assert response.json['initialized']

    response = flask_app_client.get('/api/v1/users/admin_user_initialized')
    assert response.status_code == 200
    assert response.json['initialized']  # now we True

    # Check user has all permissions
    user = User.find(email=valid_email)
    assert user.is_active
    assert user.is_admin
    assert user.is_contributor
    assert user.is_exporter
    assert user.is_internal
    assert user.is_privileged
    assert user.is_researcher
    assert user.is_staff
    assert user.is_user_manager
    assert user.in_alpha
    assert user.in_beta

    # clean up
    assert user is not None
    user.delete()
