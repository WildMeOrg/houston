# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests import utils

PATH = '/api/v1/encounters'


def test_read_encounters(flask_app_client, researcher_1):
    # pylint: disable=invalid-name
    with flask_app_client.login(researcher_1, auth_scopes=('encounters:read',)):
        response = flask_app_client.get(PATH)
    utils.validate_list_response(response, 200)


def test_read_passthroughs(flask_app_client, researcher_1):
    # pylint: disable=invalid-name
    with flask_app_client.login(researcher_1, auth_scopes=('passthroughs:read',)):
        site_name_response = flask_app_client.get(
            '/api/v1/passthroughs/default/site-name'
        )
        garbage_response = flask_app_client.get('/api/v1/passthroughs/garbage/fubar')
    # @jon what should this actually be returning. This test should be hitting the passthrough get
    # functions and is not. Any ideas why not?
    assert site_name_response.status_code == 200
    assert garbage_response.status_code == 401
