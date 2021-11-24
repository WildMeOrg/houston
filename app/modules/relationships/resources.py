# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Relationships resources
--------------------------
"""

import logging

from flask import request
from flask_login import current_user
from flask_restx_patched import Resource
from flask_restx._http import HTTPStatus

from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation

from . import parameters, schemas
from .models import Relationship


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace(
    'relationships', description='Relationships'
)  # pylint: disable=invalid-name


@api.route('/')
class Relationships(Resource):
    """
    Manipulations with Relationships.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Relationship,
            'action': AccessOperation.READ,
        },
    )
    @api.login_required(oauth_scopes=['relationships:read'])
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseRelationshipSchema(many=True))
    def get(self, args):
        """
        List of Relationship.

        Returns a list of Relationship starting from ``offset`` limited by ``limit``
        parameter.
        """
        return Relationship.query.offset(args['offset']).limit(args['limit'])

    # @api.permission_required(
    #     permissions.ModuleAccessPermission,
    #     kwargs_on_request=lambda kwargs: {
    #         'module': Relationship,
    #         'action': AccessOperation.WRITE,
    #     },
    # )
    # @api.login_required(oauth_scopes=['relationships:write'])
    @api.parameters(parameters.CreateRelationshipParameters())
    @api.response(schemas.DetailedRelationshipSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Relationship.
        """

        log.debug(' $$$$$$$$$$$$$$$$$$$$$$$$$ Tryyyinnna POST!  ')

        import utool as ut

        request_in = {}
        import json

        try:
            request_in_ = json.loads(request.data)
            request_in.update(request_in_)
        except Exception:
            pass

        log.debug('WHAT ARE THE RELATIONSHIP ARGS: ' + str(request_in))

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Relationship'
        )

        if (
            request_in['individual_1_guid']
            and request_in['individual_2_guid']
            and request_in['individual_1_role']
            and request_in['individual_2_role']
        ):
            with context:
                relationship = Relationship(
                    request_in['individual_1_guid'],
                    request_in['individual_2_guid'],
                    request_in['individual_1_role'],
                    request_in['individual_2_role'],
                )
                db.session.add(relationship)
                for member in relationship.individual_members:
                    db.session.add(member)

            rtn = {
                'success': True,
                'guid': relationship.guid,
                'type': relationship.type,
                'start_date': relationship.start_date,
                'individual_members': [],
            }
            for member in relationship.individual_members:
                each_member = {
                    'individual_role': member.individual_role,
                    'individual_guid': str(member.individual_guid),
                }
                rtn['individual_members'].append(each_member)
            # ut.embed()
            return rtn
        else:
            log.debug('FAILED TO CREATE RELATIONSHIP!')


@api.route('/<uuid:relationship_guid>')
@api.login_required(oauth_scopes=['relationships:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Relationship not found.',
)
@api.resolve_object_by_model(Relationship, 'relationship')
class RelationshipByID(Resource):
    """
    Manipulations with a specific Relationship.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['relationship'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedRelationshipSchema())
    def get(self, relationship):
        """
        Get Relationship details by ID.
        """
        return relationship

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['relationship'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['relationships:write'])
    @api.parameters(parameters.PatchRelationshipDetailsParameters())
    @api.response(schemas.DetailedRelationshipSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, relationship):
        """
        Patch Relationship details by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Relationship details.'
        )
        with context:
            parameters.PatchRelationshipDetailsParameters.perform_patch(
                args, obj=relationship
            )
            db.session.merge(relationship)
        return relationship

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['relationship'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['relationships:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, relationship):
        """
        Delete a Relationship by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to delete the Relationship.'
        )

        # import utool as ut
        # ut.embed()

        with context:
            relationship.delete()
        return None
