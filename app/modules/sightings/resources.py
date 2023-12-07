# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Sightings resources
--------------------------
"""

import json
import logging
from http import HTTPStatus
from uuid import UUID

import werkzeug
from flask import make_response, request, send_file
from flask_login import current_user  # NOQA

import app.extensions.logging as AuditLog
from app.extensions import db
from app.extensions.api import Namespace, abort
from app.modules import utils
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import CascadeDeleteException, HoustonException
from flask_restx_patched import Resource

from . import parameters, schemas
from .models import Sighting, SightingStage

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('sightings', description='Sightings')  # pylint: disable=invalid-name


def _get_annotations(enc_json):
    assert enc_json is not None
    from app.modules.annotations.models import Annotation

    if not isinstance(enc_json, dict):
        raise HoustonException(log, 'encounters needs to be a dictionary')
    anns = []
    anns_in = enc_json.get('annotations', [])
    for ann_in in anns_in:
        ann_guid = ann_in.get('guid', None)
        ann = Annotation.query.get(ann_guid)
        if not ann:
            raise HoustonException(log, f'Annotation {ann_guid} not found')
        anns.append(ann)
    return anns


@api.route('/')
class Sightings(Resource):
    """
    Manipulations with Sightings.
    """

    @api.login_required(oauth_scopes=['sightings:read'])
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Sighting,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseSightingSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Sighting.
        """
        return Sighting.query_search(args=args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Sighting,
            'action': AccessOperation.WRITE,
        },
    )
    @api.parameters(parameters.CreateSightingParameters())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Sighting - Not supported
        """
        # Now disabled. Should use AssetGroup API instead
        abort(400, 'Not supported. Use the AssetGroup POST API instead')


@api.route('/search')
@api.login_required(oauth_scopes=['sightings:read'])
class SightingElasticsearch(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Sighting,
            'action': AccessOperation.READ,
        },
    )
    @api.response(Sighting.get_elasticsearch_schema()(many=True))
    @api.paginate()
    def get(self, args):
        search = {}
        args['total'] = True
        return Sighting.elasticsearch(search, **args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Sighting,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.ElasticsearchSightingReturnSchema(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()
        args['total'] = True
        # hacky way to skip when already querying on viewers or query is "unusual"(?)
        if (
            not current_user
            or '"viewers"' in str(search)
            or 'bool' not in search
            or 'filter' not in search['bool']
            or not isinstance(search['bool']['filter'], list)
        ):
            return Sighting.elasticsearch(search, **args)
        from copy import deepcopy

        view_search = deepcopy(search)
        view_search['bool']['filter'].append(
            {'match': {'viewers': str(current_user.guid)}}
        )
        log.debug(f'doing viewer search using {view_search}')
        view_count, view_res = Sighting.elasticsearch(view_search, load=False, **args)
        return Sighting.elasticsearch(search, **args) + (view_count,)


@api.route('/export')
@api.login_required(oauth_scopes=['export:write'])
class SightingExport(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Sighting,
            'action': AccessOperation.EXPORT,
        },
    )
    def post(self):
        search = request.get_json()
        sights = Sighting.elasticsearch(search)
        if not sights:
            abort(400, 'No results to export')
        from flask import send_file

        from app.extensions.export.models import Export

        export = Export()
        ct = 0
        for sight in sights:
            if not sight.current_user_has_view_permission():
                continue
            ct += 1
            export.add(sight)
            for enc in sight.get_encounters():
                export.add(enc)
        if not ct:
            abort(400, 'No results to export')
        export.save()
        return send_file(
            export.filepath,
            mimetype='application/vnd.ms-excel',
            as_attachment=True,
            attachment_filename=export.filename,
        )


@api.route('/remove_all_empty')
@api.login_required(oauth_scopes=['sightings:write'])
class SightingRemoveEmpty(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Sighting,
            'action': AccessOperation.DELETE,
        },
    )
    def post(self):
        try:
            Sighting.remove_all_empty()
        except HoustonException as ex:
            abort(400, ex.message)


@api.route('/<uuid:sighting_guid>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Sighting not found.',
)
@api.resolve_object_by_model(Sighting, 'sighting')
class SightingByID(Resource):
    """
    Manipulations with a specific Sighting.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedSightingSchema())
    def get(self, sighting):
        """
        Get Sighting details by ID.
        """
        return sighting

    @api.login_required(oauth_scopes=['sightings:write'])
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.parameters(parameters.PatchSightingDetailsParameters())
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(schemas.DetailedSightingSchema())
    def patch(self, args, sighting):
        """
        Patch Sighting details by ID.
        """
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Sighting details.'
        )
        with context:
            try:
                delete_cascade_individual = (
                    request.headers.get(
                        'x-allow-delete-cascade-individual', 'false'
                    ).lower()
                    == 'true'
                )
                delete_cascade_sighting = (
                    request.headers.get(
                        'x-allow-delete-cascade-sighting', 'false'
                    ).lower()
                    == 'true'
                )
                state = {
                    'delete-individual': delete_cascade_individual,
                    'delete-sighting': delete_cascade_sighting,
                }
                parameters.PatchSightingDetailsParameters.perform_patch(
                    args, sighting, state=state
                )
            except CascadeDeleteException as ex:
                if ex.vulnerable_sighting_guids or ex.vulnerable_individual_guids:
                    # just replicating how DELETE /api/v1/encounters/GUID handles it
                    vul_sight = (
                        ex.vulnerable_sighting_guids
                        and ex.vulnerable_sighting_guids[0]
                        or None
                    )
                    vul_indiv = (
                        ex.vulnerable_individual_guids
                        and ex.vulnerable_individual_guids[0]
                        or None
                    )
                    abort(
                        400,
                        'Remove failed because it would cause a delete cascade',
                        vulnerableIndividualGuid=vul_indiv,
                        vulnerableSightingGuid=vul_sight,
                    )

                if ex.deleted_sighting_guids:
                    # Presuming it is this sighting that has been deleted so we cannot return it
                    return {}
            except ValueError as ex:
                abort(409, str(ex))
            except HoustonException as ex:
                abort(ex.status_code, ex.message)
            db.session.merge(sighting)

        AuditLog.patch_object(log, sighting, args, duration=timer.elapsed())

        return sighting

    @api.login_required(oauth_scopes=['sightings:write'])
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, sighting):
        """
        Delete a Sighting by ID.
        """
        delete_individual = (
            request.headers.get('x-allow-delete-cascade-individual', 'false').lower()
            == 'true'
        )
        success, response = sighting.delete_frontend_request(delete_individual)
        if not success:
            if 'vulnerableIndividual' in response:
                abort(
                    400,
                    'Delete failed because it would cause a delete cascade',
                    vulnerableIndividualGuid=response.get('vulnerableIndividual'),
                )
            else:
                abort(400, 'Delete failed')
        else:
            # we have to roll our own response here (to return) as it seems the only way we can add a header
            #   (which we are using to denote the encounter DELETE also triggered a sighting DELETE, since
            #   no body is returned on a 204 for DELETE
            resp = make_response()
            resp.status_code = 204

            individual_ids = response.get('deletedIndividuals')
            if individual_ids:
                resp.headers['x-deletedIndividual-guids'] = ', '.join(individual_ids)

            return resp


@api.route('/<uuid:sighting_guid>/featured_asset_guid')
@api.resolve_object_by_model(Sighting, 'sighting')
class FeaturedAssetGuidBySightingID(Resource):
    """
    Featured Asset guid set and retrieval.
    """

    @api.login_required(oauth_scopes=['sightings:read'])
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.READ,
        },
    )
    def get(self, sighting):
        """
        Get featured Asset guid.
        """
        from app.modules.sightings.schemas import FeaturedAssetOnlySchema

        asset_schema = FeaturedAssetOnlySchema()
        return asset_schema.dump(sighting)

    @api.login_required(oauth_scopes=['sightings:write'])
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.WRITE,
        },
    )
    def post(self, sighting):

        request_in = json.loads(request.data)

        context = api.commit_or_abort(
            db.session,
            default_error_message='Failed to update Sighting.featured_asset_guid.',
        )
        featured_asset_guid = request_in.get('featured_asset_guid', None)

        success = False

        if utils.is_valid_uuid_string(featured_asset_guid):
            sighting.set_featured_asset_guid(UUID(featured_asset_guid, version=4))
            with context:
                db.session.merge(sighting)
            success = True
        return {'success': success}


@api.route('/<uuid:sighting_guid>/sage_identified/<uuid:job_guid>', doc=False)
@api.login_required(oauth_scopes=['sightings:write'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Sighting not found.',
)
@api.resolve_object_by_model(Sighting, 'sighting')
class SightingSageIdentified(Resource):
    """
    Indentification of Sighting complete
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.WRITE_INTERNAL,
        },
    )
    def post(self, sighting, job_guid):
        try:
            # Don't expect the response to have the full JSON response, leads to errors in Sage that can't be handled
            # sighting.identified(job_guid, json.loads(request.data))

            # Instead, use the data we already have to fetch the result from Sage
            from .tasks import fetch_sage_identification_result

            promise = fetch_sage_identification_result.delay(
                str(sighting.guid), str(job_guid)
            )
            log.info(f'Fetching Identification for Sighting:{sighting.guid} in celery')
            return str(promise.id)
        except HoustonException as ex:
            abort(ex.status_code, ex.message, errorFields=ex.get_val('error', 'Error'))


@api.route('/<uuid:sighting_guid>/rerun_id')
@api.login_required(oauth_scopes=['sightings:write'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Sighting not found.',
)
@api.resolve_object_by_model(Sighting, 'sighting')
class SightingRerunId(Resource):
    """
    Rerun ID for whole Sighting
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.response(schemas.DetailedSightingSchema())
    def post(self, sighting):
        try:
            req = json.loads(request.data)
            from app.modules.asset_groups.metadata import (
                AssetGroupMetadata,
                AssetGroupMetadataError,
            )

            log.warning(req)
            if isinstance(req, list) and len(req) > 0:
                try:
                    AssetGroupMetadata.validate_id_configs(req, 'id_configs')
                except AssetGroupMetadataError as error:
                    abort(error.status_code, error.message)
                sighting.id_configs = req
            sighting.stage = SightingStage.identification
            # progress_overwrite will ensure we have a new Progress started on sighting
            sighting.ia_pipeline(progress_overwrite=True)
            return sighting
        except HoustonException as ex:
            abort(ex.status_code, ex.message, errorFields=ex.get_val('error', 'Error'))


@api.route('/<uuid:sighting_guid>/id_result')
@api.login_required(oauth_scopes=['sightings:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Sighting not found.',
)
@api.resolve_object_by_model(Sighting, 'sighting')
class SightingIdResult(Resource):
    """
    Get of latest Sighting ID data
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.READ,
        },
    )
    def get(self, sighting):
        try:
            return sighting.get_id_result()
        except HoustonException as ex:
            abort(ex.status_code, ex.message, errorFields=ex.get_val('error', 'Error'))


@api.route('/<uuid:sighting_guid>/annotations/src/<uuid:annotation_guid>')
@api.login_required(oauth_scopes=['sightings:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Sighting not found.',
)
@api.resolve_object_by_model(Sighting, 'sighting')
class SightingIdResultAnnotationSrcAsset(Resource):
    """
    Get the asset for an annotation in the Sighting's ID data
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.READ,
        },
    )
    def get(self, sighting, annotation_guid):
        from app.modules.annotations.models import Annotation

        annotation = Annotation.query.get(annotation_guid)
        if not annotation:
            # Sanity check, this should always pass
            abort(code=HTTPStatus.NOT_FOUND, message='Annotation not found.')

        asset = annotation.asset

        # First, check if the user owns the asset
        if not asset.user_is_owner(current_user):
            # Next, check if the sighting has this annotation in it's ID results
            annotation_guids = sighting.get_matched_annotation_guids()
            if annotation_guid not in annotation_guids:
                # Last, final attempt to see if a user can load this ID result from any collaborator's sightings
                if not asset.user_can_access(current_user):
                    abort(
                        code=HTTPStatus.NOT_FOUND,
                        message='Annotation not found in the ID results for this Sighting.',
                    )

        # The user is allowed to view the asset, but not the original source.  Only show the derived "mid" version
        format = 'mid'
        cls = type(asset.git_store)
        cls.ensure_store(asset.git_store_guid)
        try:
            asset_format_path = asset.get_or_make_format_path(format)
        except Exception:
            logging.exception('Got exception from get_or_make_format_path()')
            raise werkzeug.exceptions.NotImplemented

        return send_file(asset_format_path, asset.DERIVED_MIME_TYPE)


@api.route('/<uuid:sighting_guid>/featured_image', doc=False)
@api.login_required(oauth_scopes=['sightings:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Sighting not found.',
)
@api.resolve_object_by_model(Sighting, 'sighting')
class SightingImageByID(Resource):
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.READ,
        },
    )
    def get(self, sighting):
        from io import StringIO

        asset_guid = sighting.get_featured_asset_guid()
        if not asset_guid:
            return send_file(StringIO(), attachment_filename='sighting_image.jpg')
        else:
            from app.modules.assets.models import Asset

            asset = Asset.query.get(asset_guid)
            if not asset:
                return send_file(StringIO(), attachment_filename='sighting_image.jpg')
            try:
                image_path = asset.get_or_make_master_format_path()
            except HoustonException as ex:
                abort(ex.status_code, ex.message)
            return send_file(image_path, attachment_filename='sighting_image.jpg')


@api.route('/debug/<uuid:sighting_guid>', doc=False)
@api.login_required(oauth_scopes=['sightings:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Sighting not found.',
)
@api.resolve_object_by_model(Sighting, 'sighting')
class SightingDebugByID(Resource):
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.READ_DEBUG,
        },
    )
    @api.response(schemas.DebugSightingSchema())
    def get(self, sighting):
        return sighting


@api.route('/jobs/<uuid:sighting_guid>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Sighting not found.',
)
@api.resolve_object_by_model(Sighting, 'sighting')
class SightingJobsByID(Resource):
    """
    The Sighting jobs details.
    """

    @api.login_required(oauth_scopes=['sightings:read'])
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.READ_DEBUG,
        },
    )
    def get(self, sighting):
        """
        Get Sighting job details by ID.
        """

        return sighting.get_job_debug()
