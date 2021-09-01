# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Audit Logs resources
--------------------------
"""

import logging

from flask_restx_patched import Resource
from flask_restx._http import HTTPStatus

from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation

from . import schemas
from .models import AuditLog


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('audit_logs', description='Audit_logs')  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['audit_logs:read'])
class AuditLogs(Resource):
    """
    Manipulations with Audit Logs.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AuditLog,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    def get(self, args):
        """
        List of AuditLog.

        This is the list of module names and the guids for the module objects for which there are audit logs
        """
        unique_logs = []
        all_logs = AuditLog.query.all()
        for log_entry in all_logs:
            name_and_guid = {'name': log_entry.module_name, 'guid': log_entry.item_guid}
            if name_and_guid not in unique_logs and name_and_guid != {
                'name': None,
                'guid': None,
            }:
                unique_logs.append(name_and_guid)

        # Need to manually apply offset and limit after the unique list is created
        return unique_logs[args['offset'] : args['limit'] - args['offset']]


@api.route('/<uuid:audit_log_guid>')
@api.login_required(oauth_scopes=['audit_logs:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='AuditLog not found.',
)
class AuditLogByID(Resource):
    """
    Manipulations with a specific AuditLog.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AuditLog,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedAuditLogSchema())
    def get(self, audit_log_guid):
        """
        Get AuditLog details by the ID of the item that is being logged about.
        """
        audit_logs = AuditLog.query.filter(AuditLog.item_guid == audit_log_guid).first()
        return audit_logs
