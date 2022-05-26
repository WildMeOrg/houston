# -*- coding: utf-8 -*-
from unittest import mock

import pytest
from requests import Response

import app.version
from tests.utils import extension_unavailable


@pytest.mark.skipif(
    extension_unavailable('sage', 'edm'), reason='Sage or EDM extension disabled'
)
def test_site_info(flask_app_client):
    with mock.patch('flask.current_app.sage.get_dict') as sage_get_dict:
        with mock.patch('flask.current_app.edm.get_dict') as edm_get_dict:
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
            edm_get_dict.return_value = {
                'date': '2021-04-07 02:23:04 -0700',
                'built': '2021-04-07 09:25:46+00:00',
                'hash': '477dac40056d1f722579bffa949b8979fc7e6e31',
                'branch': 'next-gen',
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
        'edm': {
            'date': '2021-04-07 02:23:04 -0700',
            'built': '2021-04-07 09:25:46+00:00',
            'hash': '477dac40056d1f722579bffa949b8979fc7e6e31',
            'branch': 'next-gen',
        },
    }


@pytest.mark.skipif(
    extension_unavailable('sage', 'edm'), reason='Sage or EDM extension disabled'
)
def test_site_info_api_error(flask_app_client):
    with mock.patch('flask.current_app.sage.get_dict') as sage_get_dict:
        with mock.patch('flask.current_app.edm.get_dict') as edm_get_dict:
            not_found = Response()
            not_found.status_code = 404
            sage_get_dict.return_value = not_found
            edm_get_dict.return_value = not_found
            # both sage and edm returns 404
            resp = flask_app_client.get('/api/v1/site-settings/site-info/')

    assert resp.status_code == 200
    assert resp.content_type == 'application/json'
    assert resp.json == {
        'houston': {
            'version': app.version.version,
            'git_version': app.version.git_revision,
        },
        'sage': '<Response [404]>',
        'edm': '<Response [404]>',
    }
