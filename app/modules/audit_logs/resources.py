# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Audit Logs resources
--------------------------
"""

import logging
from http import HTTPStatus

from flask import request

from app.extensions.api import Namespace
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from flask_restx_patched import Resource

from . import schemas
from .models import AuditLog
from .parameters import GetAuditLogFaultsParameters, GetAuditLogParameters

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
    @api.response(schemas.DetailedAuditLogSchema(many=True))
    @api.paginate(GetAuditLogParameters())
    def get(self, args):
        """
        List of AuditLogs.
        """
        query = AuditLog.query_search(args=args)

        if 'module_name' in args:
            query = query.filter_by(module_name=args['module_name'])

        return query


@api.route('/search')
@api.login_required(oauth_scopes=['audit_logs:read'])
class AuditLogElasticsearch(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AuditLog,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedAuditLogSchema(many=True))
    @api.paginate()
    def get(self, args):
        search = {}
        args['total'] = True
        return AuditLog.elasticsearch(search, **args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AuditLog,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedAuditLogSchema(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()

        args['total'] = True
        return AuditLog.elasticsearch(search, **args)


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
            .all()
        )


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
    @api.response(schemas.DetailedAuditLogSchema(many=True))
    @api.paginate(GetAuditLogFaultsParameters())
    def get(self, args):
        """
        Get AuditLog details by the ID of the item that is being logged about.
        """
        import app.extensions.logging as AuditLogExtension  # NOQA

        if 'fault_type' in args:
            faults = AuditLog.query.filter_by(audit_type=args['fault_type'])
        else:
            faults = AuditLog.query.filter(
                (AuditLog.audit_type == AuditLogExtension.AuditType.HoustonFault.value)
                | (AuditLog.audit_type == AuditLogExtension.AuditType.BackEndFault.value)
                | (AuditLog.audit_type == AuditLogExtension.AuditType.FrontEndFault.value)
            )

        return faults
