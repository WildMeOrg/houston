# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Audit_logs resources RESTful API
-----------------------------------------------------------
"""
from flask_marshmallow import base_fields

from app.extensions.api.parameters import PaginationParameters


class GetCollaborationParameters(PaginationParameters):
    module_name = base_fields.String(
        description='Optional Module Required', required=False
    )
