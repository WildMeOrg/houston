# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests import utils
import pytest

from tests.utils import module_unavailable

PATH = '/api/v1/encounters/'


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_read_encounters(flask_app_client, researcher_1):
    # pylint: disable=invalid-name
    with flask_app_client.login(researcher_1, auth_scopes=('encounters:read',)):
        response = flask_app_client.get(PATH)
    utils.validate_list_response(response, 200)


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_get_encounter_not_found(flask_app_client):
    response = flask_app_client.get(f'{PATH}not-found')
    assert response.status_code == 404
