# -*- coding: utf-8 -*-
"""
Task resources utils
-------------
"""
import json
from tests import utils as test_utils

PATH = '/api/v1/tasks/'


def create_task(flask_app_client, user, title, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('tasks:write',)):
        response = flask_app_client.post(
            PATH, content_type='application/json', data=json.dumps({'title': title})
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'title'})
        assert response.json['title'] == title
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def patch_task(flask_app_client, task_guid, user, data, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('tasks:write',)):
        response = flask_app_client.patch(
            '%s%s' % (PATH, task_guid),
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'title'})
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_task(flask_app_client, user, task_guid, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('tasks:read',)):
        response = flask_app_client.get('%s%s' % (PATH, task_guid))

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'title'})
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_all_tasks(flask_app_client, user, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('tasks:read',)):
        response = flask_app_client.get(PATH)

    if expected_status_code == 200:
        test_utils.validate_list_response(response, 200)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def delete_task(flask_app_client, user, task_guid, expected_status_code=204):
    with flask_app_client.login(user, auth_scopes=('tasks:delete',)):
        response = flask_app_client.delete('%s%s' % (PATH, task_guid))

    if expected_status_code == 204:
        assert response.status_code == 204
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
