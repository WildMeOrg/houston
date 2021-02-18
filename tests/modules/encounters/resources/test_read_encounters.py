# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests import utils

PATH = '/api/v1/encounters/'


def test_read_encounters(flask_app_client, researcher_1):
    # pylint: disable=invalid-name
    with flask_app_client.login(researcher_1, auth_scopes=('encounters:read',)):
        response = flask_app_client.get(PATH)
    utils.validate_list_response(response, 200)
