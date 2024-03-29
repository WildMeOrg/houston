# -*- coding: utf-8 -*-
import datetime
import enum
import logging
import pprint
import uuid

from flask import current_app, request

from app.extensions import HoustonModel, db
from app.extensions.email import Email  # , _format_datetime

log = logging.getLogger(__name__)
pp = pprint.PrettyPrinter(indent=2)


class EmailTypes(str, enum.Enum):
    invite = 'invite'
    confirm = 'confirm'
    receipt = 'receipt'


class EmailRecord(db.Model, HoustonModel):
    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    recipient = db.Column(db.String, index=True, nullable=False)
    email_type = db.Column(db.Enum(EmailTypes), index=True, nullable=False)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'type={self.email_type}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.emails.schemas import BaseEmailRecordSchema

        return BaseEmailRecordSchema


class RecordedEmail(Email):
    def __init__(self, *args, **kwargs):
        self.email_type = None
        super(RecordedEmail, self).__init__(*args, **kwargs)

    def send_message(self, *args, **kwargs):
        response = super(RecordedEmail, self).send_message(*args, **kwargs)
        try:
            if self.email_type is not None:
                status = response.get('status', None)
                if status in ['sent']:
                    for recipient in self.recipients:
                        record = EmailRecord(
                            recipient=recipient, email_type=self.email_type
                        )
                        with db.session.begin():
                            db.session.add(record)
        except Exception:
            pass
        return response


class ErrorEmail(RecordedEmail):
    def __init__(self, subject, data={}, **kwargs):

        assert 'recipients' not in kwargs
        recipients = current_app.config.get('MAIL_ERROR_RECIPIENTS', None)
        assert recipients is not None
        kwargs['recipients'] = recipients

        super(ErrorEmail, self).__init__(subject, **kwargs)

        timestamp = datetime.datetime.now(tz=current_app.config.get('TIMEZONE'))
        global_data = {
            'timestamp': timestamp,
            'request': request,
        }
        global_data.update(data)
        global_data_ = pp.pformat(global_data)

        tempate_kwargs = {
            'error_data': global_data_,
        }
        self.template('email.error.jinja2', **tempate_kwargs)


class SystemErrorEmail(ErrorEmail):
    def __init__(self, module, description, data={}, **kwargs):
        subject = 'System Error'

        local_data = {
            'module': module,
            'description': description,
        }
        local_data.update(data)

        super(SystemErrorEmail, self).__init__(subject, data=local_data, **kwargs)
