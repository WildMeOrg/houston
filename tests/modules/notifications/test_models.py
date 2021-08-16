# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging

from app.modules.notifications.models import (
    Notification,
    NotificationType,
    UserNotificationPreferences,
    NOTIFICATION_DEFAULTS,
    SystemNotificationPreferences,
)

log = logging.getLogger(__name__)


def test_get_notification_prefs(db, researcher_1):
    preferences = UserNotificationPreferences.get_user_preferences(researcher_1)
    assert set(preferences.keys()) == set(NOTIFICATION_DEFAULTS)
    system_prefs = SystemNotificationPreferences.get()

    system_prefs.preferences['companionship_request'] = False

    preferences = UserNotificationPreferences.get_user_preferences(researcher_1)
    assert set(preferences.keys()) > set(NOTIFICATION_DEFAULTS)
    assert 'companionship_request' in preferences.keys()

    notification_preferences = UserNotificationPreferences(user=researcher_1)
    with db.session.begin():
        db.session.add(notification_preferences)
    try:
        notification_preferences.preferences = {
            'end of the world': {
                'email': True,
            }
        }

        preferences = UserNotificationPreferences.get_user_preferences(researcher_1)
        assert 'end of the world' in preferences.keys()
    finally:
        with db.session.begin():
            db.session.delete(notification_preferences)


def test_notification_message(db, researcher_1, researcher_2):
    data = {'requester': researcher_1.guid}
    notification = Notification.create(
        NotificationType.collab_request, researcher_2, data
    )
    with db.session.begin():
        db.session.add(notification)
    try:
        chans = notification.channels_to_send()
        assert set({'Rest API', 'email'}) == set(chans.keys())

    finally:
        with db.session.begin():
            db.session.delete(notification)
