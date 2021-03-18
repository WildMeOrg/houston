# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest


@pytest.mark.parametrize(
    'http_method,http_path,expected_code',
    (
        ('GET', '/api/v1/users/', 401),
        ('GET', '/api/v1/users/11111111-1111-1111-1111-111111111111', 404),
        ('PATCH', '/api/v1/users/11111111-1111-1111-1111-111111111111', 404),
        ('GET', '/api/v1/users/me', 401),
    ),
)
def test_unauthorized_access(http_method, http_path, expected_code, flask_app_client):
    response = flask_app_client.open(method=http_method, path=http_path)
    assert response.status_code == expected_code
