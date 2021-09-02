# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Collaborations resources
--------------------------
"""

import logging
import json
import uuid

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
from app.modules.users import permissions


from . import parameters, schemas
from .models import Collaboration


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
    @api.response(schemas.DetailedCollaborationSchema(many=True))
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
        from app.modules.users.models import User

        req = json.loads(request.data)
        other_user_guid = req.get('user_guid')
        other_user = User.query.get(other_user_guid)
        if not other_user:
            abort(400, f'User with guid {other_user_guid} not found')

        if not other_user.is_researcher:
            abort(400, f'User with guid {other_user_guid} is not a researcher')

        for collab_assoc in current_user.user_collaboration_associations:
            if other_user in collab_assoc.collaboration.get_users():
                log.warning(
                    f'User {current_user.email} attempted repeated collaboration with {other_user.email}'
                )
                return collab_assoc.collaboration

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Collaboration'
        )
        user_guids = [current_user.guid, uuid.UUID(other_user_guid)]
        initiator_states = [True, False]
        states = ['approved', 'pending']
        if current_user.is_user_manager:
            second_user_guid = req.get('second_user_guid')
            second_user = User.query.get(second_user_guid)
            if not second_user:
                abort(400, f'User with guid {second_user_guid} not found')
            if not second_user.is_researcher:
                abort(400, f'User with guid {second_user_guid} is not a researcher')

            user_guids = [other_user_guid, second_user_guid]
            states = ['approved', 'approved']
            initiator_states = [False, False]

        with context:

            collaboration = Collaboration(
                user_guids=user_guids,
                approval_states=states,
                initiator_states=initiator_states,
            )
            db.session.add(collaboration)

        # Once created notify the pending user to accept
        collaboration.notify_pending_users()

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
