# -*- coding: utf-8 -*-
from unittest import mock

import pytest
from requests import Response

import app.version
from tests.utils import extension_unavailable


@pytest.mark.skipif(extension_unavailable('sage'), reason='Sage extension disabled')
def test_site_info(flask_app_client):
    with mock.patch('flask.current_app.sage.get_dict') as sage_get_dict:
        sage_get_dict.return_value = {
            'status': {
                'success': True,
                'code': 200,
                'message': '',
                'cache': -1,
            },
            'response': {
                'version': '3.5.1.dev23',
            },
        }
        resp = flask_app_client.get('/api/v1/site-settings/site-info/')
    assert resp.status_code == 200
    assert resp.content_type == 'application/json'
    assert resp.json == {
        'houston': {
            'version': app.version.version,
            'git_version': app.version.git_revision,
        },
        'sage': {
            'version': '3.5.1.dev23',
        },
    }


@pytest.mark.skipif(extension_unavailable('sage'), reason='Sage extension disabled')
def test_site_info_api_error(flask_app_client):
    with mock.patch('flask.current_app.sage.get_dict') as sage_get_dict:
        not_found = Response()
        not_found.status_code = 404
        sage_get_dict.return_value = not_found
        # sage returns 404
        resp = flask_app_client.get('/api/v1/site-settings/site-info/')

    assert resp.status_code == 200
    assert resp.content_type == 'application/json'
    assert resp.json == {
        'houston': {
            'version': app.version.version,
            'git_version': app.version.git_revision,
        },
        'sage': '<Response [404]>',
    }


def test_public_data(flask_app_client):
    resp = flask_app_client.get('/api/v1/site-settings/public-data/').json
    # can't really check much validity, only that something came back
    assert 'num_users' in resp
