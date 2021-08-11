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
    expected_error='',
):
    with flask_app_client.login(user, auth_scopes=('collaborations:write',)):
        response = flask_app_client.patch(
            '%s%s' % (PATH, collaboration_guid),
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid'})
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
        assert response.json['message'] == expected_error, response.json['message']

    return response


def read_collaboration(
    flask_app_client, user, collaboration_guid, expected_status_code=200
):
    if user:
        with flask_app_client.login(user, auth_scopes=('collaborations:read',)):
            response = flask_app_client.get(f'{PATH}{collaboration_guid}')
    else:
        response = flask_app_client.get(f'{PATH}{collaboration_guid}')

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid'})
    elif expected_status_code == 404:
        test_utils.validate_dict_response(response, expected_status_code, {'message'})
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_all_collaborations(flask_app_client, user, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('collaborations:read',)):
        response = flask_app_client.get(PATH)

    if expected_status_code == 200:
        test_utils.validate_list_response(response, 200)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response
