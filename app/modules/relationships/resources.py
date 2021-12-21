# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Relationships resources
--------------------------
"""

import logging

from flask import request
from app.modules.individuals.models import Individual
from flask_restx_patched import Resource
from flask_restx._http import HTTPStatus
from datetime import datetime  # NOQA

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

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Relationship,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['relationships:write'])
    @api.parameters(parameters.CreateRelationshipParameters())
    @api.response(schemas.DetailedRelationshipSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Relationship.
        """
        from app.extensions.elapsed_time import ElapsedTime
        import app.extensions.logging as AuditLog  # NOQA

        timer = ElapsedTime()

        request_in = {}
        import json

        try:
            request_in_ = json.loads(request.data)
            request_in.update(request_in_)
        except Exception:
            pass

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Relationship'
        )

        if (
            request_in['individual_1_guid']
            and request_in['individual_2_guid']
            and request_in['individual_1_role']
            and request_in['individual_2_role']
        ):

            if _user_has_write_permission_on_both_individuals(
                request_in['individual_1_guid'], request_in['individual_2_guid']
            ):
                with context:
                    relationship = Relationship(
                        request_in['individual_1_guid'],
                        request_in['individual_2_guid'],
                        request_in['individual_1_role'],
                        request_in['individual_2_role'],
                    )
                    if 'type' in request_in:
                        relationship.type = request_in['type']
                    if 'start_date' in request_in:
                        try:
                            relationship.start_date = datetime.strptime(
                                request_in['start_date']
                            )
                        except ValueError as ve:
                            AuditLog.backend_fault(
                                log,
                                ve,
                                self,
                            )
                    if 'end_date' in request_in:
                        try:
                            relationship.start_date = datetime.strptime(
                                request_in['end_date']
                            )
                        except ValueError as ve:
                            AuditLog.backend_fault(
                                log,
                                ve,
                                self,
                            )

                    db.session.add(relationship)
                    for member in relationship.individual_members:
                        db.session.add(member)
                AuditLog.user_create_object(log, relationship, duration=timer.elapsed())
            else:
                AuditLog.backend_fault(
                    log,
                    'Current user lacks permission to create Relationship for one or both Individuals.',
                    self,
                )
            return relationship


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
        from app.extensions.elapsed_time import ElapsedTime
        import app.extensions.logging as AuditLog  # NOQA

        individual_1_guid = relationship.individual_members[0].individual_guid
        individual_2_guid = relationship.individual_members[1].individual_guid
        if _user_has_write_permission_on_both_individuals(
            individual_1_guid, individual_2_guid
        ):
            timer = ElapsedTime()
            context = api.commit_or_abort(
                db.session, default_error_message='Failed to delete the Relationship.'
            )
            with context:
                relationship.delete()
                AuditLog.delete_object(log, relationship, duration=timer.elapsed())
        else:
            AuditLog.backend_fault(
                log,
                'Current user lacks permission to delete Relationship for one or both Individuals.',
                self,
            )
        return None


def _user_has_write_permission_on_both_individuals(individual_1_guid, individual_2_guid):
    individual_1 = Individual.query.get(individual_1_guid)
    individual_2 = Individual.query.get(individual_2_guid)
    if (
        individual_1.current_user_has_edit_permission()
        and individual_2.current_user_has_edit_permission()
    ):
        return True
    return False
