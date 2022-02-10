# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Audit Logs resources
--------------------------
"""

import logging

from flask_restx_patched import Resource
from flask_restx._http import HTTPStatus
from flask_login import current_user

from app.extensions.api import Namespace
from app.extensions.logging import Logging as AuditExt
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
    def get(self, args):
        """
        List of AuditLogs.

        This is the list of the last N audit logs
        """
        from sqlalchemy import desc

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
        returned_data = []
        for log_item in reversed(all_logs):

            # This means that non staff users will get less than limit each time
            if (
                log_item.audit_type == AuditExt.AuditType.HoustonFault
                or log_item.audit_type == AuditExt.AuditType.BackEndFault
                or log_item.audit_type == AuditExt.AuditType.FrontEndFault
            ):
                if not current_user.is_privileged:
                    # Non privileged users don't see faults
                    continue

            data = {
                'timestamp': log_item.created,
                'type': log_item.audit_type,
                'executor': log_item.user_email,
                'duration': log_item.duration,
                'module_name': log_item.module_name,
                'item_guid': log_item.item_guid,
                'message': log_item.message,
            }

            returned_data.append(data)

        return returned_data


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
        audit_logs = AuditLog.query.filter_by(item_guid=audit_log_guid).all()
        return audit_logs


@api.route('/faults')
@api.login_required(oauth_scopes=['audit_logs:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='AuditLog not found.',
)
class AuditLogFault(Resource):
    """
    Manipulations with the AuditLogs for a specific object.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AuditLog,
            'action': AccessOperation.READ_PRIVILEGED,
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
            all_logs = (
                AuditLog.query.filter_by(AuditLog.module_name == args['fault_type'])
                .order_by(AuditLog.created)
                .all()
            )
        else:
            all_logs = (
                AuditLog.query.filter_by(
                    audit_type=(
                        AuditLogExtension.AuditType.FrontEndFault
                        or AuditLogExtension.AuditType.BackEndFault
                        or AuditLogExtension.AuditType.HoustonFault
                    )
                )
                .order_by(AuditLog.created)
                .all()
            )

        # all_logs is now the logs of interest ordered by the time created, oldest first.
        # What we actually want to return the 'limit' type and message values for the most recently audited items.
        # So we need to reverse all_logs first
        all_logs.reverse()

        # Need to manually apply offset and limit after the unique list is created
        return all_logs[args['offset'] : args['limit'] - args['offset']]
