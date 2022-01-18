# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Missions resources
--------------------------
"""

import logging

from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus
from flask_login import current_user  # NOQA

from app.extensions import db
from app.extensions.api import Namespace
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from . import parameters, schemas
from .models import Mission


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('missions', description='Missions')  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['missions:read'])
class Missions(Resource):
    """
    Manipulations with Missions.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Mission,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(parameters.ListMissionParameters())
    @api.response(schemas.BaseMissionSchema(many=True))
    def get(self, args):
        """
        List of Mission.

        Returns a list of Mission starting from ``offset`` limited by ``limit``
        parameter.
        """
        search = args.get('search', None)
        if search is not None and len(search) == 0:
            search = None

        missions = Mission.query_search(search)

        return missions.order_by(Mission.guid).offset(args['offset']).limit(args['limit'])

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Mission,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['missions:write'])
    @api.parameters(parameters.CreateMissionParameters())
    @api.response(schemas.DetailedMissionSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Mission.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Mission'
        )
        args['owner_guid'] = current_user.guid
        mission = Mission(**args)
        # User who creates the mission gets added to it
        mission.add_user(current_user)
        with context:
            db.session.add(mission)

        db.session.refresh(mission)

        return mission


@api.route('/<uuid:mission_guid>')
@api.login_required(oauth_scopes=['missions:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Mission not found.',
)
@api.resolve_object_by_model(Mission, 'mission')
class MissionByID(Resource):
    """
    Manipulations with a specific Mission.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedMissionSchema())
    def get(self, mission):
        """
        Get Mission details by ID.
        """
        return mission

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['missions:write'])
    @api.parameters(parameters.PatchMissionDetailsParameters())
    @api.response(schemas.DetailedMissionSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, mission):
        """
        Patch Mission details by ID.
        """

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Mission details.'
        )
        with context:
            parameters.PatchMissionDetailsParameters.perform_patch(args, obj=mission)
            db.session.merge(mission)
        return mission

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['missions:delete'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, mission):
        """
        Delete a Mission by ID.
        """
        mission.delete_cascade()
        return None
