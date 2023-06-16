# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API AccountRequest resources
--------------------------
"""

import logging
from http import HTTPStatus

from app.extensions import db
from app.extensions.api import Namespace
from app.modules.auth.utils import recaptcha_required
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from flask_restx_patched import Resource

from . import parameters, schemas
from .models import AccountRequest

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace(
    'account-requests', description='AccountRequest Checks'
)  # pylint: disable=invalid-name


@api.route('/')
class AccountRequests(Resource):
    """
    Manipulations with AccountRequest Checking.
    """

    @api.login_required(oauth_scopes=['account_requests:read'])
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AccountRequest,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseAccountRequestSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of AccountRequest.
        """
        return AccountRequest.query

    # no login_required cuz this is anon usage
    @recaptcha_required
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AccountRequest,
            'action': AccessOperation.WRITE,
        },
    )
    @api.parameters(parameters.CreateAccountRequestParameters())
    @api.response(schemas.BaseAccountRequestSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of AccountRequest.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new AccountRequest'
        )
        with context:
            account_request = AccountRequest(**args)
            db.session.add(account_request)
        return account_request
