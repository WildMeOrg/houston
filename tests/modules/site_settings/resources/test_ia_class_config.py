# -*- coding: utf-8 -*-


def test_get_ia_class_config(flask_app_client):

    path = '/api/v1/site-settings/ia_classes'
    response = flask_app_client.get(path)
    response_data = response.json
    assert 'success' in response_data and response_data['success'] is True
