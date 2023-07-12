# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Annotations resources
--------------------------
"""

import json
import logging
from http import HTTPStatus

from flask import request

import app.extensions.logging as AuditLog
from app.extensions import db
from app.extensions.api import Namespace, abort
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException
from flask_restx_patched import Resource

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
        from app.extensions.elapsed_time import ElapsedTime
        from app.modules.asset_groups.models import AssetGroup, AssetGroupSightingStage
        from app.modules.assets.models import Asset
        from app.modules.encounters.models import Encounter

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
                message = f'Asset {asset_guid} is in {len(ags)} asset group sightings'
                AuditLog.audit_log_object_warning(log, asset, message)
                log.warning(message)
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
        try:
            # needs to be after the add to ensure asset is valid
            annotation.sync_with_sage()
        except HoustonException as ex:
            abort(400, ex.message)
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


@api.route('/matching_set/query/<uuid:annotation_guid>')
@api.login_required(oauth_scopes=['annotations:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Annotation not found.',
)
@api.resolve_object_by_model(Annotation, 'annotation')
class AnnotationMatchingSetQueryByID(Resource):
    """
    Info about matching-set queries (the search criteria, not results)
    for a given Annotation.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['annotation'],
            'action': AccessOperation.READ,
        },
    )
    def get(self, annotation):
        """
        Returns the default query for the Annotation.
        """
        return annotation.get_matching_set_default_query()

    def post(self, annotation):
        """
        Accepts a query via body, then returns the "resolved" query
        as it would be used.  (which may include some modifications.)
        """
        request_in = json.loads(request.data)
        return annotation.resolve_matching_set_query(request_in)


@api.route('/matching_set/<uuid:annotation_guid>')
@api.login_required(oauth_scopes=['annotations:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Annotation not found.',
)
@api.resolve_object_by_model(Annotation, 'annotation')
# right now load=False is default behavior, so this only returns guids.
# however, in the event this is desired to be full Annotations, uncomment:
# @api.response(schemas.BaseAnnotationSchema(many=True))
class AnnotationMatchingSetByID(Resource):
    """
    Returns actual matching set (Annotations) for a given Annotation.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['annotation'],
            'action': AccessOperation.READ,
        },
    )
    def get(self, annotation):
        """
        Returns the set based on default query for the Annotation.
        """
        return annotation.get_matching_set(load=False)

    def post(self, annotation):
        """
        Accepts a query via body, then returns matching set based on the "resolved" query
        as it would be used.  (which may include some modifications.)
        """
        request_in = json.loads(request.data)
        return annotation.get_matching_set(request_in, load=False)


@api.route('/identify/<uuid:annotation_guid>')
@api.login_required(oauth_scopes=['annotations:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Annotation not found.',
)
@api.resolve_object_by_model(Annotation, 'annotation')
# right now load=False is default behavior, so this only returns guids.
# however, in the event this is desired to be full Annotations, uncomment:
# @api.response(schemas.BaseAnnotationSchema(many=True))
class AnnotationIdentifyByID(Resource):
    """
    Initiate identification on an Annotation (with optional matching-set Elasticsearch query passed via body).
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['annotation'],
            'action': AccessOperation.READ,
        },
    )
    def post(self, annotation):
        """
        Accepts an optional matching-set query via body.  Uses default matching-set if none provided.
        """
        request_in = json.loads(request.data)
        job_count = annotation.send_to_identification(request_in)
        return {'job_count': job_count}


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


@api.route('/sage-heatmaps/src/<string:filename>')
class AnnotationSageHeatmap(Resource):
    def get(self, filename):
        import os

        from flask import current_app, send_file

        if '/' in filename:  # prevent dir-roaming
            abort(code=HTTPStatus.NOT_FOUND)

        # TODO make this a path in sightings (or etc) cuz it is duplicated there
        filepath = os.path.join(
            current_app.config.get('FILEUPLOAD_BASE_PATH', '/tmp'),
            'sage-heatmaps',
            filename,
        )
        if not os.path.exists(filepath):
            abort(code=HTTPStatus.NOT_FOUND)
        return send_file(filepath, 'image/jpeg')
