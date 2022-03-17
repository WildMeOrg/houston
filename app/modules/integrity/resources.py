# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Integrity resources
--------------------------
"""

import logging

from flask import request
from flask_restx_patched import Resource
from flask_restx._http import HTTPStatus

from app.extensions import db
from app.extensions.api import Namespace
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation

from . import parameters, schemas
from .models import Integrity


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace(
    'integrity-checks', description='Integrity Checks'
)  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['integrity:read'])
class IntegrityChecks(Resource):
    """
    Manipulations with Integrity Checking.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Integrity,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseIntegritySchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Integrity.
        """
        return Integrity.query

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Integrity,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['integrity:write'])
    @api.parameters(parameters.CreateIntegrityParameters())
    @api.response(schemas.BaseIntegritySchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Integrity.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Integrity'
        )
        with context:
            integrity = Integrity(**args)
            db.session.add(integrity)
        return integrity


@api.route('/search')
@api.login_required(oauth_scopes=['integrity:read'])
class IntegrityElasticsearch(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Integrity,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseIntegritySchema(many=True))
    @api.paginate()
    def get(self, args):
        search = {}
        args['total'] = True
        return Integrity.elasticsearch(search, **args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Integrity,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseIntegritySchema(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()

        args['total'] = True
        return Integrity.elasticsearch(search, **args)


@api.route('/<uuid:integrity_guid>')
@api.login_required(oauth_scopes=['integrity:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Integrity not found.',
)
@api.resolve_object_by_model(Integrity, 'integrity')
class IntegrityByID(Resource):
    """
    Manipulations with a specific Integrity.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['integrity'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseIntegritySchema())
    def get(self, integrity):
        """
        Get Integrity details by ID.
        """
        return integrity

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['integrity'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['integrity:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, integrity):
        """
        Delete an Integrity by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to delete the Integrity.'
        )
        with context:
            db.session.delete(integrity)
        return None
