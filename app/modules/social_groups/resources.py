# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Social Groups resources
--------------------------
"""

import logging
from flask import request
from flask_restx_patched import Resource
from flask_restx._http import HTTPStatus
from app.utils import HoustonException
from app.extensions import db
from app.extensions.api import abort, Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
import app.extensions.logging as AuditLog

from . import parameters, schemas
from .models import SocialGroup
import json

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace(
    'social-groups', description='Social Groups'
)  # pylint: disable=invalid-name


def validate_members(input_data):
    from app.modules.individuals.models import Individual
    from app.modules.site_settings.models import SiteSetting

    current_roles = {}
    permitted_role_data = json.loads(SiteSetting.get_string('social_group_roles'))
    for member_guid in input_data:

        individual = Individual.query.get(member_guid)
        if not individual:
            raise HoustonException(
                log, f'Social Group member {member_guid} does not match an individual'
            )
        if not individual.current_user_has_view_permission():
            raise HoustonException(
                log, f'Social Group member {member_guid} not accessible by user'
            )
        role = input_data[member_guid].get('role')
        if not role:
            # individuals permitted to have no role
            continue

        if role not in permitted_role_data.keys():
            raise HoustonException(log, f'Social Group role {role} not supported')
        elif permitted_role_data[role]['multipleInGroup']:
            if current_roles.get(role):
                raise HoustonException(log, f'Can only have one {role} in a group')
            current_roles[role] = True


@api.route('/')
@api.login_required(oauth_scopes=['social-groups:read'])
class SocialGroups(Resource):
    """
    Manipulations with Social Groups.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': SocialGroup,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseSocialGroupSchema(many=True))
    def get(self, args):
        """
        List of SocialGroup.

        Returns a list of SocialGroup starting from ``offset`` limited by ``limit``
        parameter.
        """
        return SocialGroup.query.offset(args['offset']).limit(args['limit'])

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': SocialGroup,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['social-groups:write'])
    @api.parameters(parameters.CreateSocialGroupParameters())
    @api.response(schemas.DetailedSocialGroupSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of SocialGroup.
        """
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()
        req = json.loads(request.data)
        members = req.get('members')
        try:
            validate_members(members)
        except HoustonException as ex:
            abort(ex.status_code, ex.message)

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new SocialGroup'
        )
        with context:
            # members and name are definitely there as they are required parameters
            social_group = SocialGroup(members, args.get('name'))
            db.session.add(social_group)
        AuditLog.user_create_object(log, social_group, duration=timer.elapsed())
        return social_group


@api.route('/<uuid:social_group_guid>')
@api.login_required(oauth_scopes=['social-groups:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='SocialGroup not found.',
)
@api.resolve_object_by_model(SocialGroup, 'social_group')
class SocialGroupByID(Resource):
    """
    Manipulations with a specific SocialGroup.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['social_group'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedSocialGroupSchema())
    def get(self, social_group):
        """
        Get SocialGroup details by ID.
        """
        return social_group

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['social_group'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['social-groups:write'])
    @api.parameters(parameters.PatchSocialGroupDetailsParameters())
    @api.response(schemas.DetailedSocialGroupSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, social_group):
        """
        Patch SocialGroup details by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update SocialGroup details.'
        )
        with context:
            parameters.PatchSocialGroupDetailsParameters.perform_patch(
                args, obj=social_group
            )
            db.session.merge(social_group)
        return social_group

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['social_group'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['social-groups:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, social_group):
        """
        Delete a SocialGroup by ID.
        """

        social_group.delete()
        return None
