# -*- coding: utf-8 -*-
import app.version


def test_site_info(flask_app_client):
    resp = flask_app_client.get('/api/v1/site-info/')
    assert resp.status_code == 200
    assert resp.content_type == 'application/json'
    assert resp.json == {
        'houston': {
            'version': app.version.version,
            'git_version': app.version.git_revision,
        },
    }
