# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from app.modules.emails.models import RecordedEmail, EmailTypes, EmailRecord
from app.extensions.email import Email
from app.modules.site_settings.models import SiteSetting
import uuid


test_recipient = str(uuid.uuid4()) + '-test@example.com'


def _prep_sending(flask_app):
    assert flask_app.config[
        'TESTING'
    ]  # this should only run in TESTING (non-sending) mode
    flask_app.config['MAIL_OVERRIDE_RECIPIENTS'] = None

    # this mocks using mailchimp, but wont send since we are in TESTING
    SiteSetting.set('email_service', string='mailchimp')
    SiteSetting.set('email_service_username', string='testing_' + str(uuid.uuid4()))
    SiteSetting.set('email_service_password', string='testing_' + str(uuid.uuid4()))


def _cleanup_sending():
    # gets rid of system_guid as well (important for other tests)
    SiteSetting.query.delete()


def test_basic_send(flask_app):
    _prep_sending(flask_app)
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
    _cleanup_sending()


def test_validity(flask_app):
    _prep_sending(flask_app)
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
    _cleanup_sending()


def test_template():
    msg = RecordedEmail(recipients=[test_recipient])
    args = {
        'subject': 'TEST_SUBJECT',
        'body': 'TEST_BODY',
    }
    msg.template('misc/blank', **args)
    assert msg._template_found

    # note: these assume the misc/blank templates do not change
    assert msg.subject == args['subject']
    assert msg.body == args['body']

    # now we just test a bad template to make sure it fails
    msg.template('fubar_' + str(uuid.uuid4()))
    assert not msg._template_found
    _cleanup_sending()
