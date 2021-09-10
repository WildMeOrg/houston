# -*- coding: utf-8 -*-
"""
notification resources utils
-------------
"""
import json
from tests import utils as test_utils

PATH = '/api/v1/notifications/'


def create_notification(
    flask_app_client, user, data, expected_status_code=200, expected_error=''
):
    if user:
        with flask_app_client.login(user, auth_scopes=('notifications:write',)):
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
        test_utils.validate_dict_response(response, 200, {'guid'})
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


def patch_notification(
    flask_app_client,
    notification_guid,
    user,
    data,
    expected_status_code=200,
    expected_error='',
):
    with flask_app_client.login(user, auth_scopes=('notifications:write',)):
        response = flask_app_client.patch(
            '%s%s' % (PATH, notification_guid),
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


def read_notification(
    flask_app_client, user, notification_guid, expected_status_code=200
):
    if user:
        with flask_app_client.login(user, auth_scopes=('notifications:read',)):
            response = flask_app_client.get(f'{PATH}{notification_guid}')
    else:
        response = flask_app_client.get(f'{PATH}{notification_guid}')

    expected_keys = {
        'guid',
        'is_read',
        'message_type',
        'sender_name',
        'sender_email',
        'message_values',
    }
    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, expected_keys)
    elif expected_status_code == 404:
        test_utils.validate_dict_response(response, expected_status_code, {'message'})
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_all_notifications(flask_app_client, user, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('notifications:read',)):
        response = flask_app_client.get(PATH)

    if expected_status_code == 200:
        test_utils.validate_list_response(response, 200)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def get_notifications(json_data, from_user_email, notification_type):
    return list(
        filter(
            lambda notif: notif['message_type'] == notification_type
            and notif['sender_email'] == from_user_email,
            json_data,
        )
    )
