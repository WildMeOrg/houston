# -*- coding: utf-8 -*-
def test_home(flask_app_client):
    response = flask_app_client.get('/')
    assert response.status_code == 200


def test_catchall_static_file(flask_app_client):
    response = flask_app_client.get('/index.html')
    assert response.status_code == 200


def test_catchall_not_found(flask_app_client):
    response = flask_app_client.get('/asdf')
    assert response.status_code == 404
