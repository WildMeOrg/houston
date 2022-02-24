# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Annotations resources
--------------------------
"""

import logging

from flask_restx_patched import Resource
from flask_restx._http import HTTPStatus

from app.extensions import db
from app.extensions.api import Namespace, abort
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
import app.extensions.logging as AuditLog

from . import parameters, schemas
from .models import Annotation


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('annotations', description='Annotations')  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['annotations:read'])
class Annotations(Resource):
    """
    Manipulations with Annotations.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Annotation,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseAnnotationSchema(many=True))
    def get(self, args):
        """
        List of Annotation.

        Returns a list of Annotation starting from ``offset`` limited by ``limit``
        parameter.
        """
        return Annotation.query.offset(args['offset']).limit(args['limit'])

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Annotation,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['annotations:write'])
    @api.parameters(parameters.CreateAnnotationParameters())
    @api.response(schemas.DetailedAnnotationSchema())
    @api.response(code=HTTPStatus.BAD_REQUEST)
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Annotation.
        """
        from app.modules.assets.models import Asset
        from app.modules.encounters.models import Encounter
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        if 'asset_guid' not in args:
            abort(code=HTTPStatus.BAD_REQUEST, message='Must provide an asset_guid')

        asset_guid = args.get('asset_guid', None)
        asset = Asset.query.get(asset_guid)
        if not asset:
            abort(code=HTTPStatus.BAD_REQUEST, message='asset_guid not found')
        args['asset_guid'] = asset_guid

        if 'encounter_guid' in args:
            encounter_guid = args.get('encounter_guid', None)
            encounter = Encounter.query.get(encounter_guid)
            if not encounter:
                abort(code=HTTPStatus.BAD_REQUEST, message='encounter_guid not found')
            args['encounter_guid'] = encounter_guid

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Annotation'
        )
        with context:
            annotation = Annotation(**args)
            AuditLog.user_create_object(log, annotation, duration=timer.elapsed())
            db.session.add(annotation)
        return annotation


@api.route('/<uuid:annotation_guid>')
@api.login_required(oauth_scopes=['annotations:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Annotation not found.',
)
@api.resolve_object_by_model(Annotation, 'annotation')
class AnnotationByID(Resource):
    """
    Manipulations with a specific Annotation.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['annotation'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedAnnotationSchema())
    def get(self, annotation):
        """
        Get Annotation details by ID.
        """
        return annotation

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['annotation'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['annotations:write'])
    @api.parameters(parameters.PatchAnnotationDetailsParameters())
    @api.response(schemas.DetailedAnnotationSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, annotation):
        """
        Patch Annotation details by ID.
        """
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Annotation details.'
        )
        with context:
            parameters.PatchAnnotationDetailsParameters.perform_patch(args, annotation)
            db.session.merge(annotation)
            AuditLog.patch_object(log, annotation, args, duration=timer.elapsed())

        return annotation

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['annotation'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['annotations:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, annotation):
        """
        Delete a Annotation by ID.
        """
        AuditLog.delete_object(log, annotation)
        annotation.delete()
        return None


@api.route('/jobs/<uuid:annotation_guid>')
@api.login_required(oauth_scopes=['annotations:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Annotation not found.',
)
@api.resolve_object_by_model(Annotation, 'annotation')
class AnnotationJobByID(Resource):
    """
    Jobs for a specific Annotation.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['annotation'],
            'action': AccessOperation.READ_DEBUG,
        },
    )
    def get(self, annotation):
        """
        Get Annotation job details by ID.
        """
        return annotation.get_job_debug(verbose=True)


@api.route('/debug/<uuid:annotation_guid>')
@api.login_required(oauth_scopes=['annotations:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Annotation not found.',
)
@api.resolve_object_by_model(Annotation, 'annotation')
class AnnotationDebugByID(Resource):
    """
    Jobs for a specific Annotation.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['annotation'],
            'action': AccessOperation.READ_DEBUG,
        },
    )
    def get(self, annotation):
        """
        Get Annotation debug details by ID.
        """
        return annotation.get_debug_json()

