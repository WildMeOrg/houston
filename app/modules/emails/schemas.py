# -*- coding: utf-8 -*-
"""
Serialization schemas for Encounters resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema

from .models import EmailRecord


class BaseEmailRecordSchema(ModelSchema):
    """
    Base EmailRecord schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = EmailRecord
        fields = (
            EmailRecord.guid.key,
            EmailRecord.recipient.key,
            EmailRecord.email_type.key,
        )
        dump_only = (EmailRecord.guid.key,)
