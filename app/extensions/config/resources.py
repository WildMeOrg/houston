# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods
"""
RESTful API Config resources
--------------------------
"""

import logging

from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus

from app.extensions.api import Namespace

from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation

from . import parameters
from .models import HoustonConfig

log = logging.getLogger(__name__)
api = Namespace('config/houston', description='HoustonConfig')


@api.route('/')
@api.login_required(oauth_scopes=['config.houston:read'])
class HoustonConfigs(Resource):
    """
    Manipulations with configs.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': HoustonConfig,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['config.houston:write'])
    @api.parameters(parameters.PatchHoustonConfigParameters())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args):
        """
        Patch config details by ID.
        """
        import app.extensions.logging as AuditLog  # NOQA

        response = parameters.PatchHoustonConfigParameters.perform_patch(args)

        print_args = []
        for arg in args:
            # Audit the change but not the password with it
            if arg.get('path') != '/current_password' and arg.get('op') != 'test':
                print_args.append(arg)

        AuditLog.patch(log, print_args)
        return response
