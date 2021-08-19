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

log = logging.getLogger(__name__)


def test_get_notifications(
    db, flask_app_client, researcher_1, researcher_2, user_manager_user
):

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
    notif_1_data = NotificationBuilder()
    notif_1_data.set_sender(researcher_1)
    # Just needs anything with a guid
    notif_1_data.set_collaboration(user_manager_user)

    Notification.create(NotificationType.collab_request, researcher_2, notif_1_data)
    notif_2_data = NotificationBuilder()
    notif_2_data.set_sender(researcher_2)
    Notification.create(NotificationType.raw, researcher_1, notif_2_data)

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

    assert researcher_1_notifs.json[-1]['message_type'] == 'raw'
    assert researcher_1_notifs.json[-1]['sender_email'] == researcher_2.email

    assert researcher_2_notifs.json[-1]['message_type'] == 'collaboration_request'
    assert researcher_2_notifs.json[-1]['sender_email'] == researcher_1.email

    notif_utils.read_notification(
        flask_app_client, researcher_1, researcher_2_notifs.json[-1]['guid'], 403
    )
    notif_utils.read_notification(
        flask_app_client, researcher_2, researcher_1_notifs.json[-1]['guid'], 403
    )
    notif_utils.read_notification(
        flask_app_client, researcher_1, researcher_1_notifs.json[-1]['guid']
    )
    researcher_2_notif = notif_utils.read_notification(
        flask_app_client, researcher_2, researcher_2_notifs.json[-1]['guid']
    )
    assert not researcher_2_notif.json['is_read']
    values = researcher_2_notif.json['message_values']
    assert set(values.keys()) >= set(
        {'sender_name', 'sender_email', 'collaboration_guid'}
    )


def test_patch_notification(
    db, flask_app_client, researcher_1, researcher_2, user_manager_user
):
    # Create a dummy one
    notif_1_data = NotificationBuilder()
    notif_1_data.set_sender(researcher_1)
    # Just needs anything with a guid
    notif_1_data.set_collaboration(user_manager_user)

    Notification.create(NotificationType.collab_request, researcher_2, notif_1_data)

    researcher_2_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_2
    )
    notif_guid = researcher_2_notifs.json[-1]['guid']
    data = [test_utils.patch_replace_op('is_read', True)]
    notif_utils.patch_notification(flask_app_client, notif_guid, researcher_2, data)

    res_2_notif = notif_utils.read_notification(
        flask_app_client, researcher_2, researcher_2_notifs.json[-1]['guid']
    )
    values = res_2_notif.json['message_values']
    assert set(values.keys()) >= set(
        {'sender_name', 'sender_email', 'collaboration_guid'}
    )
    assert res_2_notif.json['is_read']
