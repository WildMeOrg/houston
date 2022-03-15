# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Annotations resources
--------------------------
"""

import logging

from flask import request
from flask_restx_patched import Resource
from flask_restx._http import HTTPStatus

from app.extensions import db
from app.extensions.api import Namespace, abort
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
    @api.response(schemas.BaseAnnotationSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Annotation.
        """
        return Annotation.query_search(args=args)

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
        from app.modules.asset_groups.models import AssetGroup, AssetGroupSightingStage
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
            if isinstance(asset.git_store, AssetGroup):
                sighting_assets = asset.get_asset_sightings()
                other_sighting_assets = [
                    sa
                    for sa in sighting_assets
                    if sa.sighting_guid != encounter.sighting.guid
                ]
                if len(sighting_assets) != 0 and len(other_sighting_assets) != 0:
                    abort(
                        code=HTTPStatus.BAD_REQUEST,
                        message='Cannot add Annotation with Encounter on different Sighting',
                    )

        elif isinstance(asset.git_store, AssetGroup):
            # Asset groups have stages, missions do not
            ags = asset.git_store.get_asset_group_sightings_for_asset(asset)
            if not ags:
                abort(
                    code=HTTPStatus.BAD_REQUEST,
                    message='cannot create encounter-less annotation on asset that does not have an asset group sighting',
                )
            if len(ags) != 1:
                log.warning(f'Asset {asset_guid} is in {len(ags)} asset group sightings')
                abort(
                    code=HTTPStatus.BAD_REQUEST,
                    message='asset erroneously in multiple asset group sightings',
                )

            if ags[0].stage != AssetGroupSightingStage.curation:
                abort(
                    code=HTTPStatus.BAD_REQUEST,
                    message='cannot create encounter-less annotation on asset in asset group sighting that is not curating',
                )
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Annotation'
        )
        with context:
            annotation = Annotation(**args)
            AuditLog.user_create_object(log, annotation, duration=timer.elapsed())
            db.session.add(annotation)
        return annotation


@api.route('/search')
@api.login_required(oauth_scopes=['annotations:read'])
class AnnotationElasticsearch(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Annotation,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseAnnotationSchema(many=True))
    @api.paginate()
    def get(self, args):
        search = {}
        args['total'] = True
        return Annotation.elasticsearch(search, **args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Annotation,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseAnnotationSchema(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()
        args['total'] = True
        return Annotation.elasticsearch(search, **args)


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
