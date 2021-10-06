# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging

import pytest

from app.modules.notifications.models import (
    Notification,
    NotificationType,
    NotificationBuilder,
    UserNotificationPreferences,
    NOTIFICATION_DEFAULTS,
    SystemNotificationPreferences,
)
from app.utils import HoustonException

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


def test_notification_message(db, researcher_1, researcher_2, flask_app):
    from tests.modules.emails.test_email import _prep_sending

    builder = NotificationBuilder(researcher_1)

    # just needs something with a guid
    builder.set_collaboration(researcher_1)

    # we make user want emails in NotificationPreferences to test email-send-upon-creation
    notification_preferences = UserNotificationPreferences(user=researcher_2)
    notification_preferences.preferences = {
        NotificationType.collab_request: {'email': True, 'restAPI': True},
        NotificationType.all: {'email': True},
    }
    _prep_sending(flask_app)  # allows us to fake-send emails (enough for testing)

    notification = Notification.create(
        NotificationType.collab_request, researcher_2, builder
    )
    with db.session.begin():
        db.session.add(notification)

    # check the email we (hopefully) (did not really) sent out
    assert 'email' in notification._channels_sent
    assert 'collaboration request' in notification._channels_sent['email'].subject
    assert researcher_2.email in notification._channels_sent['email'].recipients

    try:
        chans = notification.channels_to_send()
        assert set({'restAPI', 'email'}) == set(chans.keys())

    finally:
        with db.session.begin():
            db.session.delete(notification)


def test_validate_preferences():
    from app.modules.notifications.models import NotificationPreferences

    with pytest.raises(HoustonException) as exc:
        NotificationPreferences.validate_preferences([])
    assert str(exc.value) == 'Invalid input type.'

    with pytest.raises(HoustonException) as exc:
        NotificationPreferences.validate_preferences({'random': 'value'})
    assert (
        str(exc.value)
        == 'Unknown field(s): random, options are all, collaboration_request, merge_request, raw.'
    )

    with pytest.raises(HoustonException) as exc:
        NotificationPreferences.validate_preferences({'all': {'random': True}})
    assert (
        str(exc.value) == '"all": Unknown field(s): random, options are email, restAPI.'
    )

    with pytest.raises(HoustonException) as exc:
        NotificationPreferences.validate_preferences({'all': {'restAPI': 'wrong_type'}})
    assert str(exc.value) == '"all.restAPI": Not a valid boolean.'

    with pytest.raises(HoustonException) as exc:
        NotificationPreferences.validate_preferences(
            {'all': {'restAPI': 'wrong_type'}, 'random': 'value'}
        )
    assert (
        str(exc.value)
        == '"all.restAPI": Not a valid boolean. Unknown field(s): random, options are all, collaboration_request, merge_request, raw.'
    )

    # Valid examples
    NotificationPreferences.validate_preferences({})
    NotificationPreferences.validate_preferences({'all': {'restAPI': True}})
