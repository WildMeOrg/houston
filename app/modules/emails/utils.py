# -*- coding: utf-8 -*-

import logging
import re
import enum

log = logging.getLogger(__name__)

EMAIL_PATH = 'app/modules/emails/templates/en/'
DIGEST_EMAIL_PATH = f'{EMAIL_PATH}digest/'


class EmailType(str, enum.Enum):
    raw = 'raw'
    collab_request = 'collaboration request'
    merge_request = 'individual merge request'
    password_reset = 'password reset'


class EmailUtils(object):
    @classmethod
    def build_email(cls, email_type, replacements, is_digest=False):
        assert email_type in EmailType.__members__
        path = DIGEST_EMAIL_PATH if is_digest else EMAIL_PATH
        template_filename = f'{path}{email_type}.html'
        with open(template_filename) as file:
            text = file.read()
            for key in replacements.keys():
                text = re.sub(f'@{key}@', replacements[key], text)
        return text

    @classmethod
    def _send_email_with_mailchimp(cls, email_contents):
        # TODO In future this will link in to the library to do this
        pass

    @classmethod
    def send_email(cls, email_contents):
        from app.modules.site_settings.models import SiteSetting

        email_service = SiteSetting.query.get('email_service')
        if email_service == 'mailchimp':
            cls._send_email_with_mailchimp(email_contents)
        else:
            log.warning(f'email service {email_service} not supported')
