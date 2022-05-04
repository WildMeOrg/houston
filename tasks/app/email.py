# -*- coding: utf-8 -*-

from tasks.utils import app_context_task
from app.modules.emails.models import EmailTypes
from app.extensions.email import Email
from app.modules.site_settings.models import SiteSetting


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

    SiteSetting.set('email_service', string='mailchimp')
    if username:
        SiteSetting.set('email_service_username', string=username)
    if password:
        SiteSetting.set('email_service_password', string=password)

    msg = Email(subject=subject, recipients=[recipient])
    msg.body = body
    msg.email_type = EmailTypes.invite
    resp = msg.send_message()
    return resp['success']
