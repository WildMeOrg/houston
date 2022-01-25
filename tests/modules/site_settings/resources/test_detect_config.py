# -*- coding: utf-8 -*-


def test_get_detect_config(flask_app_client):

    path = '/api/v1/site-settings/detection'
    response = flask_app_client.get(path)
    response_data = response.json
    assert 'success' in response_data and response_data['success'] is True
