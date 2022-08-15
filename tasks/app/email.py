# -*- coding: utf-8 -*-

from app.extensions.email import Email
from app.modules.emails.models import EmailTypes
from app.modules.site_settings.models import SiteSetting
from tasks.utils import app_context_task


@app_context_task(
    help={
        'username': 'Authentication username',
        'password': 'Authentication password / key',
    }
)
def send(
    context, recipient, body, subject='Codex test subject', username=None, password=None
):
    """
    Send a REAL email (currently only using Mailchimp) and optionally set Mailchimp username and/or password
    """
    from flask import current_app as app

    # app.config['MAIL_DEBUG'] = True
    # app.config['DEBUG'] = True
    app.config['MAIL_OVERRIDE_RECIPIENTS'] = None

    SiteSetting.set_key_value('email_service', 'mailchimp')
    if username:
        SiteSetting.set_key_value('email_service_username', username)
    if password:
        SiteSetting.set_key_value('email_service_password', password)

    msg = Email(subject=subject, recipients=[recipient])
    msg.body = body
    msg.email_type = EmailTypes.invite
    resp = msg.send_message()
    return resp['success']
