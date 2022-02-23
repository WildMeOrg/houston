# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

from app.modules.emails.models import RecordedEmail, EmailTypes, EmailRecord
from app.extensions.email import Email


test_recipient = str(uuid.uuid4()) + '-test@example.com'


def test_basic_send():
    test_subject = 'test subject'
    msg = RecordedEmail(test_subject, recipients=[test_recipient])
    msg.email_type = EmailTypes.invite
    msg.body = 'body'

    # outbox will track sent messages so we can verify this worked
    with msg.mail.record_messages() as outbox:
        resp = msg.send_message()
        assert resp['success']
        assert len(outbox) == 1
        assert outbox[0].subject == test_subject
        assert outbox[0].recipients[0] == test_recipient

    # this should be recorded in the db table; so lets prove it
    rec = EmailRecord.query.first()
    assert rec is not None
    assert rec.recipient == test_recipient
    assert rec.email_type == EmailTypes.invite


def test_validity():
    msg = Email('test subject', recipients=[test_recipient])
    try:
        msg.send_message()
    except ValueError as ve:
        assert 'body' in str(ve)
    msg.body = 'test content'
    try:
        msg.recipients = None
        msg.send_message()
    except ValueError as ve:
        assert 'recipients' in str(ve)


def test_template(flask_app):
    flask_app.config['MAIL_OVERRIDE_RECIPIENTS'] = ['override@example.org']
    msg = RecordedEmail(recipients=[test_recipient])
    args = {
        'subject': 'TEST_SUBJECT',
        'body': 'TEST_BODY',
    }
    msg.template('misc/blank', **args)
    assert msg._template_found
    assert msg.recipients == ['override@example.org']
    assert msg.extra_headers['X-Houston-Recipients'] == test_recipient

    # note: these assume the misc/blank templates do not change
    assert msg.subject == args['subject']
    assert msg.body == args['body']

    # now we just test a bad template to make sure it fails
    msg.template('fubar_' + str(uuid.uuid4()))
    assert not msg._template_found
