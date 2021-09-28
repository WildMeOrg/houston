# -*- coding: utf-8 -*-
"""
Collaboration resources utils
-------------
"""
import json
from tests import utils as test_utils

PATH = '/api/v1/collaborations/'


def create_collaboration(
    flask_app_client, user, data, expected_status_code=200, expected_error=''
):
    if user:
        with flask_app_client.login(user, auth_scopes=('collaborations:write',)):
            response = flask_app_client.post(
                '%s' % PATH,
                content_type='application/json',
                data=json.dumps(data),
            )
    else:
        response = flask_app_client.post(
            '%s' % PATH,
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'members'})
    elif 400 <= expected_status_code < 500:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
        assert response.json['message'] == expected_error, response.json['message']
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def patch_collaboration(
    flask_app_client,
    collaboration_guid,
    user,
    data,
    expected_status_code=200,
    expected_error=None,
):
    return test_utils.patch_via_flask(
        flask_app_client,
        user,
        scopes='collaborations:write',
        path=f'{PATH}{collaboration_guid}',
        data=data,
        response_200={'guid'},
        expected_status_code=expected_status_code,
        expected_error=expected_error,
    )


def read_collaboration(
    flask_app_client, user, collaboration_guid, expected_status_code=200
):
    return test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='collaborations:read',
        path=f'{PATH}{collaboration_guid}',
        expected_status_code=expected_status_code,
        response_200={'guid'},
    )


def read_all_collaborations(flask_app_client, user, expected_status_code=200):
    return test_utils.get_list_via_flask(
        flask_app_client,
        user,
        scopes='collaborations:read',
        path=PATH,
        expected_status_code=expected_status_code,
    )


def request_edit(
    flask_app_client,
    collaboration_guid,
    user,
    expected_status_code=200,
    expected_error=None,
):
    return test_utils.post_via_flask(
        flask_app_client,
        user,
        scopes='collaborations:write',
        path=f'{PATH}edit_request/{collaboration_guid}',
        data={},
        expected_status_code=expected_status_code,
        response_200={'guid'},
        expected_error=expected_error,
    )
