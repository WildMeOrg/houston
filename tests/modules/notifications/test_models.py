# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging

import pytest

from app.modules.notifications.models import (
    NOTIFICATION_DEFAULTS,
    Notification,
    NotificationBuilder,
    NotificationChannel,
    NotificationType,
    SystemNotificationPreferences,
    UserNotificationPreferences,
)
from app.utils import HoustonException
from tests.utils import module_unavailable

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


@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_notification_message(db, researcher_1, researcher_2, flask_app, request):
    from app.modules.collaborations.models import Collaboration

    builder = NotificationBuilder(researcher_1)

    members = [researcher_1, researcher_2]
    basic_collab = Collaboration(members, researcher_2)
    request.addfinalizer(basic_collab.delete)

    builder.set_collaboration(basic_collab)

    # we make user want emails in NotificationPreferences to test email-send-upon-creation
    researcher_2.notification_preferences = []
    notification_preferences = UserNotificationPreferences(user=researcher_2)
    notification_preferences.preferences = {
        NotificationType.collab_request.value: {'email': True, 'restAPI': True},
        NotificationType.all.value: {'email': True},
    }

    basic_collab.init_req_notification_guid = (
        None  # allows us to delete below without violating foreign key constraint
    )
    Notification.query.delete()  # make sure no existing notifications (cuz multiple=false)
    notification = Notification.create(
        NotificationType.collab_request, researcher_2, builder
    )
    with db.session.begin():
        db.session.add(notification)
    request.addfinalizer(lambda: db.session.delete(notification))

    # check the email we (hopefully) (did not really) sent out
    assert 'email' in notification._channels_sent
    sent_email = notification._channels_sent['email']
    assert 'collaboration request' in sent_email.subject
    assert researcher_2.email in sent_email.recipients
    assert 'sent you a collaboration request' in sent_email.html
    assert '</body>' in sent_email.html
    with db.session.begin():
        db.session.delete(notification_preferences)

    try:
        chans = notification.channels_to_send()
        assert set({'restAPI', 'email'}) == set(chans.keys())

    finally:
        with db.session.begin():
            db.session.delete(notification)


def test_validate_preferences():
    from app.modules.notifications.models import (
        NotificationChannel,
        NotificationPreferences,
        NotificationType,
    )

    with pytest.raises(HoustonException) as exc:
        NotificationPreferences.validate_preferences([])
    assert str(exc.value) == 'Invalid input type.'

    with pytest.raises(HoustonException) as exc:
        NotificationPreferences.validate_preferences({'random': 'value'})

    valid_options = sorted(i.value for i in NotificationType.__members__.values())
    assert (
        str(exc.value)
        == f'Unknown field(s): random, options are {", ".join(valid_options)}.'
    )

    with pytest.raises(HoustonException) as exc:
        NotificationPreferences.validate_preferences({'all': {'random': True}})
    valid_channels = sorted(i.value for i in NotificationChannel.__members__.values())
    assert (
        str(exc.value)
        == f'"all": Unknown field(s): random, options are {", ".join(valid_channels)}.'
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
        == f'"all.restAPI": Not a valid boolean. Unknown field(s): random, options are {", ".join(valid_options)}.'
    )

    # Valid examples
    NotificationPreferences.validate_preferences({})
    NotificationPreferences.validate_preferences({'all': {'restAPI': True}})


def test_system_notification_preferences_outdated(db):
    system_prefs = SystemNotificationPreferences.get()
    # Let's say "all" is newly added in the code and isn't in the
    # database object
    del system_prefs.preferences[NotificationType.all]
    # and the database object doesn't have "email" for "collab_request"
    del system_prefs.preferences[NotificationType.collab_request][
        NotificationChannel.email
    ]
    system_prefs.preferences = system_prefs.preferences
    with db.session.begin():
        db.session.merge(system_prefs)

    # Should be missing "all"
    assert system_prefs != NOTIFICATION_DEFAULTS
    # But doing SystemNotificationPreferences.get() again should add "all"
    assert SystemNotificationPreferences.get().preferences == NOTIFICATION_DEFAULTS
