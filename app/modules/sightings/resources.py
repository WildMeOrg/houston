# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Sightings resources
--------------------------
"""

import json
import logging
from uuid import UUID

import werkzeug
from flask import current_app, make_response, request, send_file
from flask_login import current_user  # NOQA

import app.extensions.logging as AuditLog
from app.extensions import db
from app.extensions.api import Namespace, abort
from app.modules import utils
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus

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
    @api.response(Sighting.get_elasticsearch_schema()(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()

        args['total'] = True
        return Sighting.elasticsearch(search, **args)


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
    def get(self, sighting):
        """
        Get Sighting details by ID.
        """

        # note: should probably _still_ check edm for: stale cache, deletion!
        #      user.edm_sync(version)
        rtn = sighting.get_detailed_json()
        rtn['pipeline_status'] = sighting.get_pipeline_status()
        return rtn

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
    def patch(self, args, sighting):
        """
        Patch Sighting details by ID.
        """
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()
        houston_args = [
            arg
            for arg in args
            if arg['path']
            in parameters.PatchSightingDetailsParameters.PATH_CHOICES_HOUSTON
        ]

        edm_args = [
            arg
            for arg in args
            if arg['path'] in parameters.PatchSightingDetailsParameters.PATH_CHOICES_EDM
        ]

        if edm_args:
            log.debug(f'wanting to do edm patch on args={edm_args}')

            # we pre-check any annotations we will want to attach to new encounters

            # list of lists of annotations for each encounter (if applicable)
            enc_anns = []
            # list of initial data (used for setting .time)
            enc_json_data = []
            try:
                for arg in edm_args:
                    if arg.get('path', None) == '/encounters' and (
                        arg.get('op', None) == 'add' or arg.get('op', None) == 'replace'
                    ):
                        enc_json = arg.get('value', {})
                        anns = _get_annotations(enc_json)
                        enc_anns.append(anns)
                        enc_json_data.append(enc_json)

            except HoustonException as ex:
                message = f'_get_annotations failed {ex.message}'
                AuditLog.audit_log_object_warning(log, sighting, message)
                log.warning(message)
                abort(code=400, message=ex.message)

            result = None
            try:
                (
                    response,
                    response_data,
                    result,
                ) = current_app.edm.request_passthrough_parsed(
                    'sighting.data',
                    'patch',
                    {'data': edm_args},
                    sighting.guid,
                    request_headers=request.headers,
                )
            except HoustonException as ex:
                if isinstance(ex.message, dict):
                    message = ex.message.get('details', ex.message)
                else:
                    message = ex.message
                abort(ex.status_code, message)

            # changed something on EDM, remove the cache
            sighting.remove_cached_edm_data()

            if 'deletedSighting' in result:
                message = f'EDM triggered self-deletion of {sighting} result={result}'
                AuditLog.audit_log_object_warning(log, sighting, message)
                log.warning(message)
                response_data['threatened_sighting_id'] = str(sighting.guid)
                sighting.delete_cascade()  # this will get rid of our encounter(s) as well so no need to rectify_edm_encounters()
                sighting = None
                return response_data

            sighting.rectify_edm_encounters(result.get('encounters'), current_user)
            assert len(enc_anns) == len(enc_json_data)
            # if we have enc_anns (len=N, N > 0), these should map to the last N encounters in this sighting
            if len(enc_anns) > 0:
                enc_res = result.get('encounters', [])
                # enc_res *should* be in order added (e.g. sorted by version)
                # note however, i am not 100% sure if sightings.encounters is in same order!  it appears to be in all my testing.
                #  in the event it proves not to be, we should trust enc_res order and/or .version on each of sighting.encounters
                assert len(enc_res) == len(
                    sighting.encounters
                )  # more just a sanity-check
                assert len(enc_anns) <= len(
                    sighting.encounters
                )  # which ones were added, basically
                i = 0
                offset = len(sighting.encounters) - len(enc_anns)
                while i < len(enc_anns):
                    log.debug(
                        f'enc_len={len(sighting.encounters)},offset={offset},i={i}: onto encounters[{offset+i}] setting {enc_anns[i]}'
                    )
                    sighting.encounters[offset + i].annotations = enc_anns[i]
                    sighting.encounters[offset + i].set_time_from_data(enc_json_data[i])
                    i += 1

            new_version = result.get('version', None)
            if new_version is not None:
                sighting.version = new_version
                context = api.commit_or_abort(
                    db.session,
                    default_error_message='Failed to update Sighting version.',
                )
                with context:
                    db.session.merge(sighting)

        if houston_args:
            if not edm_args:
                # regular houston-patching
                context = api.commit_or_abort(
                    db.session, default_error_message='Failed to update Sighting details.'
                )
            else:
                # irregular houston-patching, where we need to report that EDM data was set if houston setting failed
                context = api.commit_or_abort(
                    db.session,
                    default_error_message='Failed to update Sighting details.',
                    code=417,  # Arbitrary choice (Expectation Failed)
                    fields_written=edm_args,
                )
            with context:
                parameters.PatchSightingDetailsParameters.perform_patch(
                    houston_args, sighting
                )
                db.session.merge(sighting)

        AuditLog.patch_object(log, sighting, args, duration=timer.elapsed())

        sighting_response = sighting.get_detailed_json()
        if isinstance(sighting_response, dict):
            return sighting_response
        else:
            # sighting might be deleted, return the original patch response_data
            return response_data

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
        try:
            deleted_ids = sighting.delete_from_edm_and_houston(request)
        except HoustonException as ex:
            edm_status_code = ex.get_val('edm_status_code', 400)
            message = f'Sighting.delete {sighting.guid} failed: ({ex.status_code} / edm={edm_status_code}) {ex.message}'
            AuditLog.audit_log_object_warning(log, sighting, message)
            log.warning(message)

            ex_response_data = ex.get_val('response_data', {})
            if (
                'vulnerableIndividual' in ex_response_data
                or 'vulnerableEncounter' in ex_response_data
            ):
                abort(
                    400,
                    'Delete failed because it would cause a delete cascade.',
                    vulnerableIndividualGuid=ex_response_data.get('vulnerableIndividual'),
                    vulnerableEncounterGuid=ex_response_data.get('vulnerableEncounter'),
                )
            else:
                abort(400, 'Delete failed')

        # we have to roll our own response here (to return) as it seems the only way we can add a header
        #   (which we are using to denote the encounter DELETE also triggered a individual DELETE, since
        #   no body is returned on a 204 for DELETE
        delete_resp = make_response()
        delete_resp.status_code = 204
        if deleted_ids:
            delete_resp.headers['x-deletedIndividual-guids'] = ', '.join(deleted_ids)

        return delete_resp


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
            return sighting.get_detailed_json()
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
    def get(self, sighting):
        return sighting.get_debug_json()


@api.route('/<uuid:sighting_guid>/reviewed', doc=False)
@api.login_required(oauth_scopes=['sightings:write'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Sighting not found.',
)
@api.resolve_object_by_model(Sighting, 'sighting')
class SightingReviewedByID(Resource):
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.WRITE,
        },
    )
    def post(self, sighting):
        if sighting.reviewed():
            AuditLog.audit_log_object(log, sighting, 'Reviewed')


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
