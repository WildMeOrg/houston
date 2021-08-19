# -*- coding: utf-8 -*-

import logging

log = logging.getLogger(__name__)

EMAIL_PATH = 'app/modules/emails/templates/en/'
DIGEST_EMAIL_PATH = f'{EMAIL_PATH}digest/'


class EmailUtils(object):
    @classmethod
    def _send_email_with_mailchimp(
        cls, sender_email, recipient_email, subject, email_contents
    ):
        # TODO In future this will link in to the library to do this
        pass

    @classmethod
    def _send_email_with_twilio(
        cls, sender_email, recipient_email, subject, email_contents
    ):
        # TODO In future this will link in to the library to do this
        # https://www.twilio.com/sendgrid/email-api
        pass

    @classmethod
    def send_email(cls, sender_email, recipient_email, subject, email_contents):
        from app.modules.site_settings.models import SiteSetting

        email_service = SiteSetting.query.get('email_service')
        if email_service == 'mailchimp':
            cls._send_email_with_mailchimp(
                sender_email, recipient_email, subject, email_contents
            )
        elif email_service == 'twilio':
            cls._send_email_with_twilio(
                sender_email, recipient_email, subject, email_contents
            )
        else:
            log.warning(f'email service {email_service} not supported')
