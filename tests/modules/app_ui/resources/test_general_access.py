# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import re
from urllib.parse import urlparse

import pytest
from flask import url_for


@pytest.mark.parametrize(
    'http_method,http_path',
    (
        ('GET', '/houston/'),
        ('GET', '/houston/admin_init'),
        ('GET', '/houston/internal/testing/logging'),
        ('GET', '/api/v1/'),
    ),
)
def test_frontend_page_loads(http_method, http_path, flask_app_client):
    response = flask_app_client.open(method=http_method, path=http_path)
    print(response)
    assert response.status_code == 200


def test_login_logout(flask_app, admin_user):
    client = flask_app.test_client()
    resp = client.get(url_for('backend.home'))
    content = resp.get_data().decode('utf-8')

    login_form_url = re.search('action="([^"]*)"', content).group(1)
    resp = client.post(
        login_form_url, data={'email': admin_user.email, 'password': 'Pas$w0rd'}
    )
    assert resp.status_code == 302
    assert resp.headers['Location'] == url_for('backend.home')

    resp = client.get(url_for('backend.home'))
    content = resp.get_data().decode('utf-8')
    assert 'Hello, First Middle Last' in content
    assert urlparse(url_for('backend.user_logout')).path in content

    resp = client.get(url_for('backend.user_logout'))
    assert resp.status_code == 302
    assert resp.headers['Location'] == url_for('backend.home')
