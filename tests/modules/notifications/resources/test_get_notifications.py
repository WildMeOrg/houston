# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging

from app.modules.notifications.models import Notification, NotificationType
import tests.modules.notifications.resources.utils as notif_utils

log = logging.getLogger(__name__)


def test_get_notifications(
    db, flask_app_client, researcher_1, researcher_2, user_manager_user
):

    notif_1 = None
    notif_2 = None

    try:
        # Create a couple of them
        notif_1 = Notification.create(
            NotificationType.collab_request, researcher_1, researcher_2, {}
        )
        notif_2 = Notification.create(
            NotificationType.raw, researcher_2, researcher_1, {}
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

        assert len(researcher_1_notifs.json) == 1
        assert len(researcher_2_notifs.json) == 1
        assert len(user_manager_notifs.json) == 2

        assert researcher_1_notifs.json[0]['message_type'] == 'raw'
        assert researcher_1_notifs.json[0]['sender_email'] == researcher_2.email

        assert researcher_2_notifs.json[0]['message_type'] == 'collaboration request'
        assert researcher_2_notifs.json[0]['sender_email'] == researcher_1.email

    finally:
        with db.session.begin():
            if notif_1:
                db.session.delete(notif_1)
            if notif_2:
                db.session.delete(notif_2)
