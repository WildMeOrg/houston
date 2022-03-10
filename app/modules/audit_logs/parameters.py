# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Audit_logs resources RESTful API
-----------------------------------------------------------
"""
from flask_marshmallow import base_fields

from app.extensions.api.parameters import PaginationParameters


class GetAuditLogParameters(PaginationParameters):
    module_name = base_fields.String(
        description='Optional Module Required', required=False
    )
    sort = base_fields.String(
        description='the field to sort the results by, default is "created"',
        missing='created',
    )
    reverse = base_fields.Boolean(
        description='the field to reverse the sorted results (before paging has been performed), default is True',
        missing=True,
    )
    reverse_after = base_fields.Boolean(
        description='the field to reverse the sorted results (after paging has been performed), default is True',
        missing=True,
    )


class GetAuditLogFaultsParameters(PaginationParameters):
    fault_type = base_fields.String(
        description='Optional Fault Type Required', required=False
    )
