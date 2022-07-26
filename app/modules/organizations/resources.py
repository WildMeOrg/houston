# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Organizations resources
--------------------------
"""

import logging
from http import HTTPStatus

from flask import request
from flask_login import current_user  # NOQA

from app.extensions import db
from app.extensions.api import Namespace
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from flask_restx_patched import Resource

from . import parameters, schemas
from .models import Organization

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace(
    'organizations', description='Organizations'
)  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['organizations:read'])
class Organizations(Resource):
    """
    Manipulations with Organizations.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Organization,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseOrganizationSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Organization.
        """
        return Organization.query_search(args=args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Organization,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['organizations:write'])
    @api.parameters(parameters.CreateOrganizationParameters())
    @api.response(schemas.DetailedOrganizationSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Organization.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Organization'
        )
        with context:
            args['owner_guid'] = current_user.guid
            organization = Organization(**args)
            # User who creates the org gets added to it as a member and a moderator
            organization.add_user_in_context(current_user)
            organization.add_moderator_in_context(current_user)
            db.session.add(organization)
        return organization


@api.route('/search')
@api.login_required(oauth_scopes=['organizations:read'])
class OrganizationElasticsearch(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Organization,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedOrganizationSchema(many=True))
    @api.paginate()
    def get(self, args):
        search = {}
        args['total'] = True
        return Organization.elasticsearch(search, **args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Organization,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedOrganizationSchema(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()

        args['total'] = True
        return Organization.elasticsearch(search, **args)


@api.route('/<uuid:organization_guid>')
@api.login_required(oauth_scopes=['organizations:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Organization not found.',
)
@api.resolve_object_by_model(Organization, 'organization')
class OrganizationByID(Resource):
    """
    Manipulations with a specific Organization.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['organization'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedOrganizationSchema())
    def get(self, organization):
        """
        Get Organization details by ID.
        """
        return organization

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['organization'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['organizations:write'])
    @api.parameters(parameters.PatchOrganizationDetailsParameters())
    @api.response(schemas.DetailedOrganizationSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, organization):
        """
        Patch Organization details by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Organization details.'
        )
        with context:
            parameters.PatchOrganizationDetailsParameters.perform_patch(
                args, organization
            )
            db.session.merge(organization)
        return organization

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['organization'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['organizations:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, organization):
        """
        Delete a Organization by ID.
        """
        organization.delete()
        return None
