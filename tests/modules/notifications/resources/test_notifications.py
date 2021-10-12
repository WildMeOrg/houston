# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging
import tests.utils as test_utils
from app.modules.notifications.models import (
    Notification,
    NotificationType,
    NotificationBuilder,
)
import tests.modules.notifications.resources.utils as notif_utils
import tests.modules.users.resources.utils as user_utils

log = logging.getLogger(__name__)


def get_notifications_with_guid(json_data, guid_str, notification_type, sender_guid):
    return list(
        filter(
            lambda notif: notif['message_type'] == notification_type
            and notif['sender_guid'] == sender_guid
            and notif['guid'] == guid_str,
            json_data,
        )
    )


def test_get_notifications(
    db, flask_app_client, researcher_1, researcher_2, user_manager_user
):
    # Start with no unread notifications to ensure that they are always created here
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_1)
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_2)
    notif_utils.mark_all_notifications_as_read(flask_app_client, user_manager_user)

    prev_researcher_1_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_1
    )
    prev_researcher_2_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_2
    )
    prev_user_manager_notifs = notif_utils.read_all_notifications(
        flask_app_client, user_manager_user
    )

    # Create a couple of them
    notif_to_researcher_2_data = NotificationBuilder(researcher_1)
    # Just needs anything with a guid
    notif_to_researcher_2_data.set_collaboration(user_manager_user)

    notif_to_researcher_2 = Notification.create(
        NotificationType.collab_request, researcher_2, notif_to_researcher_2_data
    )
    notif_to_researcher_1_data = NotificationBuilder(researcher_2)
    notif_to_researcher_1 = Notification.create(
        NotificationType.raw, researcher_1, notif_to_researcher_1_data
    )

    researcher_1_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_1
    )
    researcher_2_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_2
    )
    user_manager_notifs = notif_utils.read_all_notifications(
        flask_app_client, user_manager_user
    )

    assert len(researcher_1_notifs.json) == len(prev_researcher_1_notifs.json) + 1
    assert len(researcher_2_notifs.json) == len(prev_researcher_2_notifs.json) + 1
    assert len(user_manager_notifs.json) == len(prev_user_manager_notifs.json) + 2

    collab_reqs_from_researcher_1 = get_notifications_with_guid(
        researcher_2_notifs.json,
        str(notif_to_researcher_2.guid),
        'collaboration_request',
        str(researcher_1.guid),
    )
    assert len(collab_reqs_from_researcher_1) == 1

    raw_requests_from_researcher_2 = get_notifications_with_guid(
        researcher_1_notifs.json,
        str(notif_to_researcher_1.guid),
        'raw',
        str(researcher_2.guid),
    )
    assert len(raw_requests_from_researcher_2) == 1

    notif_utils.read_notification(
        flask_app_client, researcher_1, notif_to_researcher_2.guid, 403
    )
    notif_utils.read_notification(
        flask_app_client, researcher_2, notif_to_researcher_1.guid, 403
    )
    notif_utils.read_notification(
        flask_app_client, researcher_1, notif_to_researcher_1.guid
    )
    researcher_2_notif = notif_utils.read_notification(
        flask_app_client, researcher_2, notif_to_researcher_2.guid
    )

    assert not researcher_2_notif.json['is_read']
    values = researcher_2_notif.json['message_values']
    assert set(values.keys()) >= set({'collaboration_guid'})


def test_patch_notification(
    db, flask_app_client, researcher_1, researcher_2, user_manager_user
):
    # Start with no unread notifications to ensure that they are always created here
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_1)
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_2)
    notif_utils.mark_all_notifications_as_read(flask_app_client, user_manager_user)

    # Create a dummy one
    notif_1_data = NotificationBuilder(researcher_1)
    # Just needs anything with a guid
    notif_1_data.set_collaboration(user_manager_user)

    Notification.create(NotificationType.collab_request, researcher_2, notif_1_data)

    researcher_2_unread_notifs = notif_utils.read_all_unread_notifications(
        flask_app_client, researcher_2
    )

    notif_guid = researcher_2_unread_notifs.json[-1]['guid']
    notif_utils.mark_notification_as_read(flask_app_client, researcher_2, notif_guid)

    res_2_notif = notif_utils.read_notification(
        flask_app_client, researcher_2, notif_guid
    )

    values = res_2_notif.json['message_values']
    assert set(values.keys()) >= set({'collaboration_guid'})
    assert res_2_notif.json['is_read']
    researcher_2_unread_notifs = notif_utils.read_all_unread_notifications(
        flask_app_client, researcher_2
    )
    researcher_2_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_2
    )
    assert len(researcher_2_unread_notifs.json) <= len(researcher_2_notifs.json)


def test_notification_preferences(
    db, flask_app_client, researcher_1, researcher_2, user_manager_user
):
    notif_1_data = NotificationBuilder(researcher_1)
    # Just needs anything with a guid
    notif_1_data.set_collaboration(user_manager_user)

    Notification.create(NotificationType.collab_request, researcher_2, notif_1_data)

    researcher_2_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_2
    )
    collab_requests_from_res1 = notif_utils.get_unread_notifications(
        researcher_2_notifs.json, str(researcher_1.guid), 'collaboration_request'
    )

    assert len(collab_requests_from_res1) >= 1

    # Test patch of collaboration requests alone
    data = [
        test_utils.patch_replace_op(
            'notification_preferences',
            {'collaboration_request': {'restAPI': False, 'email': False}},
        )
    ]
    user_utils.patch_user(flask_app_client, researcher_2, data)
    researcher_2_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_2
    )
    collab_requests_from_res1 = notif_utils.get_unread_notifications(
        researcher_2_notifs.json, researcher_1.email, 'collaboration_request'
    )
    assert len(collab_requests_from_res1) == 0

    # Test patch of all requests
    data = [
        test_utils.patch_replace_op(
            'notification_preferences', {'all': {'restAPI': False, 'email': False}}
        )
    ]
    user_utils.patch_user(flask_app_client, researcher_2, data)
    researcher_2_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_2
    )
    collab_requests_from_res1 = notif_utils.get_unread_notifications(
        researcher_2_notifs.json, researcher_1.email, 'collaboration_request'
    )
    assert len(collab_requests_from_res1) == 0

    # Restore to previous state as otherwise all subsequent tests fail
    data = [
        test_utils.patch_replace_op(
            'notification_preferences',
            {'collaboration_request': {'restAPI': True, 'email': False}},
        )
    ]
    user_utils.patch_user(flask_app_client, researcher_2, data)
    researcher_2_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_2
    )
    collab_requests_from_res1 = notif_utils.get_unread_notifications(
        researcher_2_notifs.json, str(researcher_1.guid), 'collaboration_request'
    )

    assert len(collab_requests_from_res1) != 0
