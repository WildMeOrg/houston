# -*- coding: utf-8 -*-
def test_tus_options(flask_app_client):
    response = flask_app_client.options('/api/v1/submissions/tus')
    assert response.status_code in (200, 204)
    assert response.headers['Tus-Resumable'] == '1.0.0'
    assert int(response.headers['Tus-Max-Size']) > 0
    assert '1.0.0' in response.headers['Tus-Version'].split(',')
    assert 'creation' in response.headers['Tus-Extension'].split(',')
    assert response.data == b''
