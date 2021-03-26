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
    response = flask_app_client.post('/api/v1/users/admin_user_initialized', data=data)
    assert response.status_code == 422

    # create one
    valid_email = 'test-admin@example.com'
    data = json.dumps({'email': valid_email, 'password': 'test1234'})
    response = flask_app_client.post('/api/v1/users/admin_user_initialized', data=data)
    assert response.status_code == 200
    assert response.json['initialized']

    response = flask_app_client.get('/api/v1/users/admin_user_initialized')
    assert response.status_code == 200
    assert response.json['initialized']  # now we True

    # clean up
    user = User.find(email=valid_email)
    assert user is not None
    user.delete()
