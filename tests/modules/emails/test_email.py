# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid
from pathlib import Path

import pytest

from app.extensions.email import Email
from app.modules.emails.models import EmailRecord, EmailTypes, RecordedEmail
from app.modules.site_settings.models import SiteSetting

test_recipient = str(uuid.uuid4()) + '-test@example.com'


def test_basic_send():
    test_subject = 'test subject'
    msg = RecordedEmail(subject=test_subject, recipients=[test_recipient])
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
    msg = Email(subject='test subject', recipients=[test_recipient])
    with pytest.raises(ValueError) as ve:
        msg.send_message()
        assert 'body' in str(ve)
    assert msg.subject == 'test subject'
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


def test_email_templates():
    email_root = Path('app/templates/email/en_us/')
    for path in email_root.glob('*/*.jinja2'):
        if '_subject.jinja2' in str(path) or path.stem.startswith('blank'):
            continue
        try:
            msg = Email(recipients=[test_recipient])
            template = str(path.relative_to(email_root)).replace('.jinja2', '')
            msg.template(template)
            assert '<html' in msg.html
        except:  # NOQA
            print(f'Email Template: {path}')
            raise


def test_sender():
    msg = Email(recipients=[test_recipient])
    assert msg.sender == 'Do Not Reply <do-not-reply@localhost>'

    SiteSetting.set_key_value('email_default_sender_name', 'Site Admin')
    SiteSetting.set_key_value('email_default_sender_email', 'admin@example.org')
    msg = Email(recipients=[test_recipient])
    assert msg.sender == 'Site Admin <admin@example.org>'

    msg = Email(recipients=[test_recipient], sender='User One <user1@example.org>')
    assert msg.sender == 'User One <user1@example.org>'
