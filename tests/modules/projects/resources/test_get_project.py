# -*- coding: utf-8 -*-
def test_get_project_not_found(flask_app_client):
    response = flask_app_client.get('/api/v1/projects/wrong-uuid')
    assert response.status_code == 404
