# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
def test_basic_send(flask_app):
    from app.modules.emails.models import RecordedEmail, EmailTypes, EmailRecord
    import uuid

    # this should only run in TESTING (non-sending) mode
    assert flask_app.config['TESTING']

    flask_app.config['MAIL_OVERRIDE_RECIPIENTS'] = None
    test_subject = 'test subject'
    test_recipient = str(uuid.uuid4()) + '-test@example.com'
    msg = RecordedEmail(test_subject)
    msg.recipients = [test_recipient]
    msg.email_type = EmailTypes.invite

    # outbox will track sent messages so we can verify this worked
    with msg.mail.record_messages() as outbox:
        msg.go()
        assert len(outbox) == 1
        assert outbox[0].subject == test_subject
        assert outbox[0].recipients[0] == test_recipient

    # this should be recorded in the db table; so lets prove it
    rec = EmailRecord.query.first()
    assert rec is not None
    assert rec.recipient == test_recipient
    assert rec.email_type == EmailTypes.invite
