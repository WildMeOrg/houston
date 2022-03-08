# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
import datetime
from io import StringIO
import logging
import re
from urllib.parse import urlparse

from flask import current_app, render_template
from flask_mail import Mail, Message, email_dispatched
from jinja2 import TemplateNotFound
from premailer import Premailer
import cssutils
import htmlmin
import app.version
from app.utils import to_ascii

from flask_restx_patched import is_extension_enabled

if not is_extension_enabled('mail'):
    raise RuntimeError('Email is not enabled')


NEWLINE_TEMP_CODE = '_^_NEWLINE_CHARACTER_^_'
WEBFONTS_PLACEHOLDER_CODE = '_^_WEBFONTS_PLACEHOLDER_^_'


cssutils_log = StringIO()
cssutils_handler = logging.StreamHandler(cssutils_log)


mail = Mail()

pmail_kwargs = {
    'cssutils_logging_handler': cssutils_handler,
    'cssutils_logging_level': logging.FATAL,
    'cache_css_parsing': True,
}
pmail = None

log = logging.getLogger(__name__)


def status(message, app):
    message.status = 'sent'


email_dispatched.connect(status)


def _validate_settings():
    from app.modules.site_settings.models import SiteSetting
    from app.utils import site_email_hostname

    host_name = site_email_hostname()
    default_sender = ('Do Not Reply', f'do-not-reply@{host_name}')
    # default_sender = current_app.config.get(
    #    'MAIL_DEFAULT_SENDER', ('Do Not Reply', f'do-not-reply@{host_name}')
    # )
    sender_name = SiteSetting.get_string('email_default_sender_name', default_sender[0])
    sender_email = SiteSetting.get_string('email_default_sender_email', default_sender[1])
    current_app.config['MAIL_DEFAULT_SENDER_EMAIL'] = sender_email
    current_app.config['MAIL_DEFAULT_SENDER_NAME'] = sender_name
    current_app.config['MAIL_DEFAULT_SENDER'] = (sender_name, sender_email)

    email_service = SiteSetting.get_string('email_service')
    valid = False
    current_app.config['MAIL_SERVER'] = None

    if email_service == 'mailchimp':
        # https://mailchimp.com/developer/transactional/docs/smtp-integration/
        username = SiteSetting.get_string('email_service_username')
        password = SiteSetting.get_string('email_service_password')
        if not username or not password:
            log.error(
                'email_service=mailchimp needs both email_service_username and email_service_password set'
            )
        else:
            current_app.config['MAIL_SERVER'] = 'smtp.mandrillapp.com'
            current_app.config['MAIL_PORT'] = 587
            current_app.config['MAIL_USERNAME'] = username
            current_app.config['MAIL_PASSWORD'] = password
            valid = True

    elif email_service == 'twilio':
        # https://www.twilio.com/sendgrid/email-api
        # https://sendgrid.com/blog/create-an-smtp-server/
        log.error('email_service=twilio not yet supported')
        valid = False

    else:
        log.warning(f'SiteSetting email_service={email_service} not supported')
    return valid


def _format_datetime(dt, verbose=False):
    """
    REF: https://stackoverflow.com/a/5891598
    """

    def _suffix(d):
        return 'th' if 11 <= d <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th')

    if verbose:
        time_fmtstr = '%B {S}, %Y at %I:%M %p'
    else:
        time_fmtstr = '%B {S}, %Y'
    return dt.strftime(time_fmtstr).replace('{S}', str(dt.day) + _suffix(dt.day))


class Email(Message):
    def __init__(self, *args, **kwargs):
        from app.modules.site_settings.models import SiteSetting
        from app.utils import site_url_prefix
        import uuid

        if 'recipients' not in kwargs:
            raise AttributeError('Email() must have recipients= argument')
        if current_app.config['TESTING']:
            log.info(
                'Email is currently running with TESTING=True, so mail will not actually send.'
            )
        now = datetime.datetime.now(tz=current_app.config.get('TIMEZONE'))

        # will attempt to discover via set_language() unless specifically set
        self.language = None
        self._transaction_id = str(uuid.uuid4())
        self.template_name = None
        self.template_kwargs = {
            'site_name': SiteSetting.get_value('site.name', default='Codex'),
            'site_url_prefix': site_url_prefix(),
            'year': now.year,
            'transaction_id': self._transaction_id,
            # some of these are leftover from PR512 and may need cleanup later
            'header_image_url': SiteSetting.get_value('email_header_image_url'),
            'h1': SiteSetting.get_value('email_title_greeting'),
            'secondary_title': SiteSetting.get_value('email_secondary_title'),
            'secondary_text': SiteSetting.get_value('email_secondary_text'),
            'legal_statement': SiteSetting.get_value('email_legal_statement'),
            'unsubscribe_link': '/unsubscribe',
            'site_url': '/',
            'site_domain': urlparse(site_url_prefix()).netloc,
            'instagram_url': SiteSetting.get_value('site.links.instagramLink'),
            'twitter_url': SiteSetting.get_value('site.links.twitterLink'),
            'facebook_url': SiteSetting.get_value('site.links.facebookLink'),
            'adoption_button_text': SiteSetting.get_value('email_adoption_button_text'),
        }
        self.status = None
        self.mail = mail

        # Debugging, override all email destinations
        recipients, self.users = self._resolve_recipients(kwargs['recipients'])
        kwargs['recipients'] = recipients
        override_recipients = current_app.config.get('MAIL_OVERRIDE_RECIPIENTS', None)
        if override_recipients is not None:
            kwargs['recipients'] = override_recipients

        super(Email, self).__init__(*args, **kwargs)
        self.extra_headers = kwargs.get('extra_headers', {})
        self.extra_headers['X-Houston-Site-Name'] = to_ascii(
            SiteSetting.get_value('site.name', default='[UNKNOWN]')
        )
        self.extra_headers['X-Houston-GUID'] = SiteSetting.get_system_guid()
        self.extra_headers['X-Houston-Transaction-ID'] = self._transaction_id
        self.extra_headers['X-Houston-Version'] = app.version.version
        self.extra_headers['X-Houston-Git-Revision'] = app.version.git_revision
        if override_recipients is not None:
            self.extra_headers['X-Houston-Recipients'] = ', '.join(recipients)

    # note: in order to be able to use set_language(), recipients must be set first on the Email
    def template(self, template, **kwargs):
        self.set_language()
        global pmail
        if pmail is None:
            base_url = current_app.config.get('MAIL_BASE_URL', None)
            if base_url is not None:
                pmail_kwargs['base_url'] = base_url
            pmail = Premailer(**pmail_kwargs)  # REF: https://pypi.org/project/premailer/
        log.info('Using premailer = %r' % (pmail))

        self.template_name = template
        self.template_kwargs.update(kwargs)
        self._template_found = False
        self._render_subject()
        self._render_html()
        self._render_txt()
        if not self._template_found:
            log.warning(f'Template {template} not used; possibly invalid name')
        return self

    # this attempts to find all the possible templates to look for, considering language etc
    # this assumes template_name is a base of filenames like: NAME_html.jinja2 and NAME_txt.jinja2
    # and that NAME.jinja2 will be assumed to be html
    # valid flavor = html, txt, subject
    def _templates_to_try(self, flavor, template_name=None):
        from app.modules.site_settings.models import SiteSetting

        temps = []
        if template_name is None:
            template_name = self.template_name
        if template_name is None:
            return temps
        langs = []
        if self.language:
            langs.append(self.language)
        site_lang = SiteSetting.get_string('preferred_language', 'en_us')
        if not self.language == site_lang:
            langs.append(site_lang)
        for lang in langs:
            temps.append(f'email/{lang}/{template_name}_{flavor}.jinja2')
            if flavor == 'html':  # also try flavorless if html
                temps.append(f'email/{lang}/{template_name}.jinja2')
        return temps

    # this tries to find the best-fitting template
    def _try_templates(self, flavor, template_name=None):
        for temp in self._templates_to_try(flavor, template_name=template_name):
            try:
                rt = render_template(temp, **self.template_kwargs)
                log.debug(f'Template flavor={flavor} matched {temp}')
                self._template_found = True
                return rt
            except TemplateNotFound:
                pass
        return None

    def _render_subject(self):
        if self.subject:
            return
        self.subject = self._try_templates('subject')
        if not self.subject:
            self.subject = self._find_default_subject()

    def _find_default_subject(self):
        subj = self._try_templates('subject', template_name='misc/DEFAULT')
        if subj:
            return subj
        # we need to have *something* as a subject
        return 'A message from Codex'

    def _render_txt(self):
        if self.body:
            return
        self.body = self._try_templates('txt')

    def _render_html(self):
        if self.html:
            return

        # Render raw HTML template with Jinja2
        self.raw_html = self._try_templates('html')

        # Run Premailer
        attempt = 0
        while attempt <= 3:
            attempt += 1
            try:
                transformed_html = pmail.transform(self.raw_html)
                break
            except (cssutils.prodparser.Missing):
                pass

        # Strip out unused leftover CSS and minify before sending
        assert NEWLINE_TEMP_CODE not in transformed_html
        transformed_html_ = transformed_html.replace('\n', NEWLINE_TEMP_CODE)
        minified_css_html_ = re.sub(
            r'<style type="text/css">.*</style>', '', transformed_html_
        )
        minified_css_html = minified_css_html_.replace(NEWLINE_TEMP_CODE, '\n')
        minified_html = htmlmin.minify(
            minified_css_html,
            remove_comments=True,
            remove_empty_space=True,
            remove_all_empty_space=True,
        )

        # Add web fonts
        webfonts = [
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Assistant:200|Chango|Molle:400i&display=swap">',
            '<link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">',
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Source+Code+Pro&display=swap">',
        ]
        webfonts_html = ''.join(webfonts)
        minified_html = minified_html.replace(
            '</head>', '%s</head>' % (WEBFONTS_PLACEHOLDER_CODE,)
        )
        final_html = minified_html.replace(WEBFONTS_PLACEHOLDER_CODE, webfonts_html)
        self.html = final_html

    def attach(self, filepath, atatchment_name, attachment_type='image/png'):
        with current_app.open_resource(filepath) as asset:
            self.attach(atatchment_name, attachment_type, asset.read())

        return self

    # note: in order to not get complex and have to break one Email up into multiple, we just use the first language
    #   we find on a recipient; TODO develop a potential MultiLanguageEmail which is acually a (potential) list of Emails
    def set_language(self):
        if self.language or not self.recipients:
            return

        from app.modules.site_settings.models import SiteSetting

        for recip in self.users:
            self.language = recip.get_preferred_langauge()
            if self.language:
                return
        self.language = SiteSetting.get_string('preferred_language', 'en_us')

    def _resolve_recipients(self, recipients):
        from app.modules.users.models import User

        addresses = []
        users = []
        for recipient in recipients:
            if isinstance(recipient, User):
                users.append(recipient)
                addresses.append(recipient.email)
            else:
                addresses.append(recipient)
        return addresses, users

    def send_message(self, *args, **kwargs):
        if _validate_settings():
            if not self.body and not self.html:
                raise ValueError(
                    f'No txt/html body content; not sending email ({self.subject}, {self.recipients})'
                )
            if not self.recipients:
                raise ValueError(f'No recipients; not sending email ({self.subject})')
            mail.init_app(
                current_app
            )  # this initializes based on new MAIL_ values from _validate_settings
            # no matter what, it seems MAIL_DEFAULT_SENDER being reset by us is not be respected/used as sender here!
            #   so we forcibly override.  this may cause trouble in the future where we *want to* set .sender explicitely.  :(
            self.sender = current_app.config['MAIL_DEFAULT_SENDER']
            log.debug(
                f'Attempting to send email from {self.sender} to {self.recipients}: {self.subject} [{self._transaction_id}]'
            )
            mail.send(self)
            response = {
                'status': self.status,
                'success': True,
            }
        else:
            log.debug(
                f'Codex not configured for email; failed to send to {self.recipients}: {self.subject}'
            )
            if self.body:
                log.debug(self.body)
            if self.html:
                log.debug(self.html)
            response = {
                'status': 'Codex email not properly configured',
                'success': False,
            }
        return response
