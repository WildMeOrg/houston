# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Audit Logs resources
--------------------------
"""

import logging
from sqlalchemy import desc
from flask_restx_patched import Resource
from flask_restx._http import HTTPStatus

from app.extensions.api import Namespace
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation

from . import schemas
from .models import AuditLog
from .parameters import GetAuditLogParameters, GetAuditLogFaultsParameters


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
    @api.parameters(GetAuditLogParameters())
    @api.response(schemas.DetailedAuditLogSchema(many=True))
    def get(self, args):
        """
        List of AuditLogs.

        This is the list of the last 'limit' audit logs
        """

        if 'module_name' in args:
            all_logs = (
                AuditLog.query.filter_by(module_name=args['module_name'])
                .order_by(desc(AuditLog.created))
                .offset(args['offset'])
                .limit(args['limit'])
                .all()
            )
        else:
            all_logs = (
                AuditLog.query.order_by(desc(AuditLog.created))
                .offset(args['offset'])
                .limit(args['limit'])
                .all()
            )

        # all_logs is now the logs of interest ordered by the time created, youngest first.
        # What we actually want to return the data with oldest first so we need to reverse all_logs first
        all_logs.reverse()
        return all_logs


@api.route('/<uuid:audit_log_guid>')
@api.login_required(oauth_scopes=['audit_logs:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='AuditLog not found.',
)
class AuditLogByID(Resource):
    """
    Manipulations with the AuditLogs for a specific object.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AuditLog,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedAuditLogSchema(many=True))
    def get(self, audit_log_guid):
        """
        Get AuditLog details by the ID of the item that is being logged about.
        """
        return (
            AuditLog.query.filter_by(item_guid=audit_log_guid)
            .order_by(AuditLog.created)
            .all())


@api.route('/faults')
@api.login_required(oauth_scopes=['audit_logs:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='AuditLog not found.',
)
class AuditLogFault(Resource):
    """
    Returns the last 'limit' faults
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AuditLog,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(GetAuditLogFaultsParameters())
    @api.response(schemas.DetailedAuditLogSchema(many=True))
    def get(self, args):
        """
        Get AuditLog details by the ID of the item that is being logged about.
        """
        import app.extensions.logging as AuditLogExtension  # NOQA

        if 'fault_type' in args:
            faults = (
                AuditLog.query.filter_by(audit_type=args['fault_type'])
                .order_by(desc(AuditLog.created))
                .offset(args['offset'])
                .limit(args['limit'])
                .all()
            )
        else:
            faults = (
                AuditLog.query.filter(
                    (AuditLog.audit_type == AuditLogExtension.AuditType.HoustonFault.value)
                    | (AuditLog.audit_type == AuditLogExtension.AuditType.BackEndFault.value)
                    | (AuditLog.audit_type == AuditLogExtension.AuditType.FrontEndFault.value)
                )
                .order_by(desc(AuditLog.created))
                .offset(args['offset'])
                .limit(args['limit'])
                .all()
            )

        # Need to be reversed as they're ordered by descending to read backwards through the faults but we
        # want the list to be in order on the web page
        faults.reverse()
        return faults
