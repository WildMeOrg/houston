# -*- coding: utf-8 -*-
"""
Serialization schemas for AccountRequest resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema

from .models import AccountRequest


class BaseAccountRequestSchema(ModelSchema):
    """
    Base AccountRequest schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = AccountRequest
        fields = (
            AccountRequest.guid.key,
            AccountRequest.created.key,
            AccountRequest.name.key,
            AccountRequest.email.key,
            AccountRequest.message.key,
        )
        # dump_only = (AccountRequest.guid.key,)
