# -*- coding: utf-8 -*-
"""
Project resources utils
-------------
"""
import json
from tests import utils as test_utils

PATH = '/api/v1/encounters/'


def create_encounter(flask_app_client, user):
    with flask_app_client.login(user):
        response = flask_app_client.post(
            PATH,
            data=json.dumps({'locationId': 'PYTEST'}),
            content_type='application/javascript',
        )

    assert isinstance(response.json, dict)
    return response


def read_encounter(flask_app_client, user, enc_guid):
    with flask_app_client.login(user, auth_scopes=('encounters:read',)):
        response = flask_app_client.get('%s%s' % (PATH, enc_guid))

    assert isinstance(response.json, dict)
    return response


def delete_encounter(flask_app_client, user, enc_guid, expected_status_code=204):
    with flask_app_client.login(user, auth_scopes=('encounter:delete',)):
        response = flask_app_client.delete('%s%s' % (PATH, enc_guid))
        import utool as ut

        ut.embed()

    if expected_status_code == 204:
        assert response.status_code == 204
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
