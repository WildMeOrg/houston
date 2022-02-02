# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest


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
