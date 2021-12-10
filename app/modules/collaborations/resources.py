# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Collaborations resources
--------------------------
"""

import logging
import json

from flask import request
from flask_login import current_user  # NOQA
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus
from app.extensions.api import abort
from marshmallow import ValidationError

from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException
from app.modules.users import permissions
import app.extensions.logging as AuditLog

from . import parameters, schemas
from .models import Collaboration, CollaborationUserState


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace(
    'collaborations', description='Collaborations'
)  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['collaborations:read'])
class Collaborations(Resource):
    """
    Manipulations with Collaborations.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Collaboration,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseCollaborationSchema(many=True))
    def get(self, args):
        """
        List of Collaboration.

        Returns a list of Collaboration starting from ``offset`` limited by ``limit``
        parameter.
        """
        return Collaboration.query.offset(args['offset']).limit(args['limit'])

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Collaboration,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['collaborations:write'])
    @api.parameters(parameters.CreateCollaborationParameters())
    @api.response(schemas.DetailedCollaborationSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Collaboration.
        """
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()
        from app.modules.users.models import User

        req = json.loads(request.data)
        other_user_guid = req.get('user_guid')
        other_user = User.query.get(other_user_guid)
        if not other_user:
            abort(400, f'User with guid {other_user_guid} not found')

        if not other_user.is_active:
            abort(400, f'User with guid {other_user_guid} is not active')

        users = [current_user, other_user]
        second_user_guid = req.get('second_user_guid')
        if second_user_guid:
            if not current_user.is_user_manager:
                abort(
                    400,
                    'Logged in user is not a user manager, "second_user_guid" not allowed',
                )

            second_user = User.query.get(second_user_guid)
            if not second_user:
                abort(400, f'Second user with guid {second_user_guid} not found')

            if not second_user.is_active:
                abort(400, f'Second user with guid {second_user_guid} is not active')

            users = [other_user, second_user]

        for collab_assoc in users[0].user_collaboration_associations:
            if collab_assoc.read_approval_state == CollaborationUserState.CREATOR:
                # Dont check associations where the current user is the creator
                continue
            if users[1] in collab_assoc.collaboration.get_users():
                log.warning(
                    f'Collaboration between {users[0].email} and {users[1].email} already exists '
                    f'Collab {collab_assoc.collaboration}(attempted by {current_user.email})'
                )
                return collab_assoc.collaboration

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Collaboration'
        )

        with context:
            collaboration = Collaboration(users, current_user)
            db.session.add(collaboration)

        # Once created notify the pending user to accept
        collaboration.notify_pending_users()
        message = f'POST collaborations create collaboration between {users}'
        AuditLog.user_create_object(
            log, collaboration, msg=message, duration=timer.elapsed()
        )

        return collaboration


@api.route('/<uuid:collaboration_guid>')
@api.login_required(oauth_scopes=['collaborations:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Collaboration not found.',
)
@api.resolve_object_by_model(Collaboration, 'collaboration')
class CollaborationByID(Resource):
    """
    Manipulations with a specific Collaboration.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['collaboration'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedCollaborationSchema())
    def get(self, collaboration):
        """
        Get Collaboration details by ID.
        """
        return collaboration

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['collaboration'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['collaborations:write'])
    @api.parameters(parameters.PatchCollaborationDetailsParameters())
    @api.response(schemas.DetailedCollaborationSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, collaboration):
        """
        Patch Collaboration details by ID.
        """
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Collaboration details.'
        )
        with context:
            try:
                parameters.PatchCollaborationDetailsParameters.perform_patch(
                    args, obj=collaboration
                )
                db.session.merge(collaboration)
            except ValidationError:
                abort(
                    400, message=f"unable to set {args[0]['path']} to {args[0]['value']}"
                )
            except HoustonException as ex:
                abort(ex.status_code, ex.message)

        AuditLog.patch_object(log, collaboration, args, duration=timer.elapsed())
        return collaboration

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['collaboration'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['collaborations:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, collaboration):
        """
        Delete a Collaboration by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to delete the Collaboration.'
        )
        with context:
            db.session.delete(collaboration)
        return None


@api.route('/edit_request/<uuid:collaboration_guid>')
@api.login_required(oauth_scopes=['collaborations:write'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Collaboration not found.',
)
@api.resolve_object_by_model(Collaboration, 'collaboration')
class CollaborationEditRequest(Resource):
    """
    Request that a specific collaboration is escalated to edit
    """

    @api.response(schemas.DetailedCollaborationSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, collaboration):

        try:
            collaboration.initiate_edit_with_other_user()
        except HoustonException as ex:
            abort(ex.status_code, ex.message)
        collaboration.notify_pending_users()

        return collaboration
