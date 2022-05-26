# -*- coding: utf-8 -*-
"""
notification resources utils
-------------
"""
import json

from tests import utils as test_utils

PATH = '/api/v1/notifications/'
EXPECTED_NOTIFICATION_KEYS = {
    'guid',
    'is_read',
    'is_resolved',
    'message_type',
    'sender_name',
    'sender_guid',
    'message_values',
    'created',
}
EXPECTED_LIST_KEYS = {
    'guid',
    'is_read',
    'is_resolved',
    'message_type',
    'sender_name',
    'sender_guid',
    'created',
}


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
    expected_error=None,
):
    return test_utils.patch_via_flask(
        flask_app_client,
        user,
        scopes='notifications:write',
        path=f'{PATH}{notification_guid}',
        data=data,
        expected_status_code=expected_status_code,
        response_200={'guid'},
        expected_error=expected_error,
    )


def read_notification(
    flask_app_client, user, notification_guid, expected_status_code=200
):
    return test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='notifications:read',
        path=f'{PATH}{notification_guid}',
        expected_status_code=expected_status_code,
        response_200=EXPECTED_NOTIFICATION_KEYS,
    )


def read_all_notifications(flask_app_client, user, sub_path='', expected_status_code=200):
    return test_utils.get_list_via_flask(
        flask_app_client,
        user,
        scopes='notifications:read',
        path=f'{PATH}{sub_path}',
        expected_status_code=expected_status_code,
        expected_fields=EXPECTED_LIST_KEYS,
    )


def filter_notif_type(list_of_notif_dicts, notification_type):
    return [
        notif
        for notif in list_of_notif_dicts
        if notif['message_type'] == notification_type
    ]


def read_all_unread_notifications(flask_app_client, user, expected_status_code=200):
    return test_utils.get_list_via_flask(
        flask_app_client,
        user,
        scopes='notifications:read',
        path=f'{PATH}unread',
        expected_status_code=expected_status_code,
        expected_fields=EXPECTED_LIST_KEYS,
    )


def get_unread_notifications(json_data, from_user_guid, notification_type):
    return list(
        filter(
            lambda notif: notif['message_type'] == notification_type
            and notif['sender_guid'] == from_user_guid
            and notif['is_read'] is False,
            json_data,
        )
    )


def mark_notification_as_read(
    flask_app_client, user, notif_guid, expected_status_code=200
):
    data = [test_utils.patch_replace_op('is_read', True)]
    patch_notification(flask_app_client, notif_guid, user, data, expected_status_code)


def mark_all_notifications_as_read(flask_app_client, user):
    unread_notifs = read_all_unread_notifications(flask_app_client, user)
    for notif in unread_notifs.json:
        mark_notification_as_read(flask_app_client, user, notif['guid'])


# Not a traditional util, this deletes all notifications in the system, the reason being that when many
# notifications are used, they are marked as read and cannot be recreated. This is intentional by design
# But it means that the tests can be non deterministic in that they can work or fail depending on what has
# happened before
def delete_all_notifications(db):
    from app.modules.notifications.models import Notification

    notifs = Notification.query.all()
    for notif in notifs:
        with db.session.begin(subtransactions=True):
            db.session.delete(notif)
