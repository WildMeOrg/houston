# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Sightings resources
--------------------------
"""

import logging

from flask_login import current_user
from flask_restplus_patched import Resource
from flask_restplus._http import HTTPStatus

from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions


from . import parameters, schemas
from .models import Sighting


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('sightings', description="Sightings")  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['sightings:read'])
class Sightings(Resource):
    """
    Manipulations with Sightings.
    """

    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseSightingSchema(many=True))
    def get(self, args):
        """
        List of Sighting.

        Returns a list of Sighting starting from ``offset`` limited by ``limit``
        parameter.
        """
        return Sighting.query.offset(args['offset']).limit(args['limit'])

    @api.login_required(oauth_scopes=['sightings:write'])
    @api.parameters(parameters.CreateSightingParameters())
    @api.response(schemas.DetailedSightingSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Sighting.
        """
        context = api.commit_or_abort(
            db.session,
            default_error_message="Failed to create a new Sighting"
        )
        with context:
            sighting = Sighting(**args)
            db.session.add(sighting)
        return sighting


@api.route('/<uuid:sighting_guid>')
@api.login_required(oauth_scopes=['sightings:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description="Sighting not found.",
)
@api.resolve_object_by_model(Sighting, 'sighting')
class SightingByID(Resource):
    """
    Manipulations with a specific Sighting.
    """

    @api.response(schemas.DetailedSightingSchema())
    def get(self, sighting):
        """
        Get Sighting details by ID.
        """
        return sighting

    @api.login_required(oauth_scopes=['sightings:write'])
    @api.permission_required(permissions.WriteAccessPermission())
    @api.parameters(parameters.PatchSightingDetailsParameters())
    @api.response(schemas.DetailedSightingSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, sighting):
        """
        Patch Sighting details by ID.
        """
        context = api.commit_or_abort(
            db.session,
            default_error_message="Failed to update Sighting details."
        )
        with context:
            parameters.PatchSightingDetailsParameters.perform_patch(args, obj=sighting)
            db.session.merge(sighting)
        return sighting

    @api.login_required(oauth_scopes=['sightings:write'])
    @api.permission_required(permissions.WriteAccessPermission())
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, sighting):
        """
        Delete a Sighting by ID.
        """
        context = api.commit_or_abort(
            db.session,
            default_error_message="Failed to delete the Sighting."
        )
        with context:
            db.session.delete(sighting)
        return None