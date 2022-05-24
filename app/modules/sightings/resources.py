# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Sightings resources
--------------------------
"""

import logging

from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus
from flask_login import current_user  # NOQA
from flask import request, current_app, send_file, make_response

from app.extensions import db
from app.extensions.api import Namespace
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException

from app.extensions.api import abort
from . import parameters, schemas
from .models import Sighting, SightingStage

from app.modules import utils
import json
import os
from uuid import UUID
import app.extensions.logging as AuditLog

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('sightings', description='Sightings')  # pylint: disable=invalid-name


class SightingCleanup(object):
    def __init__(self):
        self.sighting_guid = None
        self.asset_group = None

    def rollback_and_abort(
        self,
        message='Unknown error',
        log_message=None,
        status_code=400,
        error_fields=None,
    ):
        if log_message is None:
            log_message = message
        log.error(
            f'Bailing on sighting creation: {log_message} (error_fields {error_fields})'
        )
        if self.sighting_guid is not None:
            log.warning('Cleanup removing Sighting %r from EDM' % self.sighting_guid)
            Sighting.delete_from_edm_by_guid(current_app, self.sighting_guid, request)
        if self.asset_group is not None:
            log.warning('Cleanup removing %r' % self.asset_group)
            self.asset_group.delete()
            self.asset_group = None
        abort(
            status_code,
            message,
            errorFields=error_fields,
        )


def _validate_asset_references(asset_references):

    # NOTE for simplicity i am going to assume assetReferences *share a common transaction id*  !!
    #  this will very likely always be true, but in the event it proves not to be, this will have to be altered
    #  to do multiple create_from_tus() calls

    all_references = {}  # all paths needed, keyed by transaction id
    paths_wanted = set()
    if not isinstance(asset_references, list) or len(asset_references) < 1:
        return None, None

    for reference in asset_references:
        if (
            not isinstance(reference, dict)
            or 'path' not in reference
            or 'transactionId' not in reference
        ):
            log.error('Sighting.post malformed assetReferences data: %r' % (reference))
            raise ValueError('malformed assetReference in json')
        paths_wanted.add(reference['path'])
        if reference['transactionId'] not in all_references:
            all_references[reference['transactionId']] = set()
        all_references[reference['transactionId']].add(reference['path'])

    if len(all_references.keys()) < 1:  # hmm... no one had any assetReferences!
        return None, None

    # now we make sure we have the files we need so we can abort if not (they may fail later for other reasons)
    from app.extensions.tus import tus_upload_dir

    for tid in all_references:
        for path in all_references[tid]:
            file_path = os.path.join(
                tus_upload_dir(current_app, transaction_id=tid), path
            )
            try:
                sz = os.path.getsize(file_path)  # 2for1
            except OSError as err:
                log.exception(
                    'Sighting.post OSError %r assetReferences data: %r / %r'
                    % (err, tid, path)
                )
                raise ValueError('Error with path ' + path)
            if sz < 1:
                log.error(
                    'Sighting.post zero-size file for assetReferences data: %r / %r'
                    % (tid, path)
                )
                raise ValueError('Error with path ' + path)

    return all_references, paths_wanted


def _validate_assets(assets, paths_wanted):
    if len(assets) != len(paths_wanted):
        return None
    matches = []
    for asset in assets:
        # log.info('match for %r x %r' % (asset, paths_wanted))
        if asset.path in paths_wanted:
            matches.append(asset)
    assert len(matches) == len(paths_wanted), (
        'not all assets wanted found for %r' % paths_wanted
    )
    return matches


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

        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        cleanup = SightingCleanup()
        request_in = {}
        try:
            request_in_ = json.loads(request.data)
            request_in.update(request_in_)
        except Exception:
            pass

        # i think this was official declared as law today 2021-02-24
        if (
            'encounters' not in request_in
            or not isinstance(request_in['encounters'], list)
            or len(request_in['encounters']) < 1
        ):
            cleanup.rollback_and_abort(
                'Must have at least one encounter',
                'Sighting.post empty encounters in %r' % request_in,
            )

        # we must resolve any weirdness with owner/submitter ahead of time so we can bail if problems
        pub = False
        owner = None
        submitter_guid = None
        if current_user is None or current_user.is_anonymous:
            from app.modules.users.models import User

            owner = User.get_public_user()
            pub = True
            submitter_email = request_in.get('submitterEmail', None)
            log.info(f'Anonymous asset_group posted, submitter_email={submitter_email}')
            if (
                submitter_email is not None
            ):  # if not provided, submitter_guid is allowed to be null
                exists = User.find(email=submitter_email)
                if exists is None:
                    new_inactive = User.ensure_user(
                        submitter_email, User.initial_random_password(), is_active=False
                    )
                    submitter_guid = new_inactive.guid
                    log.info(f'New inactive user created as submitter: {new_inactive}')
                elif (
                    not exists.is_active
                ):  # we trust it, what can i say?  they are inactive so its weak and public anyway
                    submitter_guid = exists.guid
                    log.info(f'Existing inactive user assigned to submitter: {exists}')
                else:  # now this is no good; this *active* user must login!  no spoofing active users.
                    cleanup.rollback_and_abort(
                        'Invalid submitter data',
                        f'Anonymous submitter using active user email {submitter_email}; rejecting',
                        status_code=403,
                    )
        else:  # logged-in user
            owner = current_user
            submitter_guid = current_user.guid

        try:
            result_data = current_app.edm.request_passthrough_result(
                'sighting.data', 'post', {'data': request_in}, ''
            )
        except HoustonException as ex:
            cleanup.rollback_and_abort(
                ex.message,
                'Sighting.post failed',
                ex.status_code,
                ex.get_val('error', 'Error'),
            )

        # Created it, need to clean it up if we rollback
        cleanup.sighting_guid = result_data['id']

        # if we get here, edm has made the sighting.  now we have to consider encounters contained within,
        # and make houston for the sighting + encounters

        # encounters via request_in and edm (result_data) need to have same count!
        if ('encounters' in request_in and 'encounters' not in result_data) or (
            'encounters' not in request_in and 'encounters' in result_data
        ):
            cleanup.rollback_and_abort(
                'Missing encounters between request_in and result',
                'Sighting.post missing encounters in one of %r or %r'
                % (request_in, result_data),
            )
        if not len(request_in['encounters']) == len(result_data['encounters']):
            cleanup.rollback_and_abort(
                'Imbalance in encounters between data and result',
                'Sighting.post imbalanced encounters in %r or %r'
                % (request_in, result_data),
            )

        enc_anns = []  # list of lists of annotations for each encounter (if applicable)
        try:
            for enc_json in request_in['encounters']:
                anns = _get_annotations(enc_json)
                enc_anns.append(anns)
        except Exception as ex:
            cleanup.rollback_and_abort(
                'Invalid encounter.annotations',
                '_get_annotations() threw %r on encounters=%r' % (ex, enc_json),
            )

        asset_references = request_in.get('assetReferences')
        try:
            all_arefs, paths_wanted = _validate_asset_references(asset_references)
        except Exception as ex:
            cleanup.rollback_and_abort(
                'Invalid assetReference data',
                '_validate_asset_references threw %r on assets=%r'
                % (ex, request_in['assetReferences']),
            )
        log.debug(
            '_validate_asset_references returned: %r, %r' % (all_arefs, paths_wanted)
        )

        asset_group = None

        if all_arefs is not None and paths_wanted is not None:
            # files seem to exist in uploads dir, so lets make
            transaction_id = next(
                iter(all_arefs)
            )  # here is where we make single-transaciton-id assumption
            from app.modules.asset_groups.models import AssetGroup

            try:
                asset_group, input_files = AssetGroup.create_from_tus(
                    'Sighting.post ' + result_data['id'],
                    owner,
                    transaction_id,
                    paths=all_arefs[transaction_id],
                    foreground=True,
                )
            except Exception as ex:
                cleanup.asset_group = asset_group
                cleanup.rollback_and_abort(
                    'Problem with encounter/assets',
                    '%r on create_from_tus transaction_id=%r paths=%r'
                    % (ex, transaction_id, all_arefs[transaction_id]),
                )
            cleanup.asset_group = asset_group

            log.info(
                'create_from_tus returned: %r => %r' % (asset_group, asset_group.assets)
            )

        sighting = Sighting(
            guid=result_data['id'],
            version=result_data.get('version', 2),
            stage=SightingStage.processed,
        )
        sighting.set_time_from_data(request_in)
        if not sighting.time:
            cleanup.rollback_and_abort(
                'Problem with sighting time/timeSpecificity values',
                f"invalid time ({request_in.get('time')}) or timeSpecificity ({request_in.get('timeSpecificity')})",
            )
        AuditLog.user_create_object(log, sighting, duration=timer.elapsed())

        assets = None
        if paths_wanted is not None:
            assets = _validate_assets(asset_group.assets, paths_wanted)
            if assets is not None:
                sighting.add_assets_no_context(assets)
        log.debug('Sighting with guid=%r is adding assets=%r' % (sighting.guid, assets))

        from app.modules.encounters.models import Encounter

        if isinstance(result_data['encounters'], list):
            assert len(result_data['encounters']) == len(enc_anns)
            i = 0
            while i < len(result_data['encounters']):
                try:
                    import uuid

                    encounter = Encounter(
                        guid=result_data['encounters'][i]['id'],
                        version=result_data['encounters'][i].get('version', 2),
                        asset_group_sighting_encounter_guid=uuid.uuid4(),
                        owner_guid=owner.guid,
                        annotations=enc_anns.pop(0),
                        submitter_guid=submitter_guid,
                        public=pub,
                    )
                    encounter.set_time_from_data(request_in['encounters'][i])
                    sighting.add_encounter(encounter)
                    i += 1
                except Exception as ex:
                    cleanup.rollback_and_abort(
                        'Problem with creating encounter: ',
                        '%r on encounter %d: enc=%r'
                        % (ex, i, request_in['encounters'][i]),
                    )

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to persist new houston Sighting'
        )
        with context:
            db.session.add(sighting)

        from app.modules.assets.schemas import DetailedAssetSchema

        asset_schema = DetailedAssetSchema(exclude=('annotations'))
        rtn = {
            'success': True,
            'result': {
                'id': str(sighting.guid),
                'version': sighting.version,
                'encounters': result_data['encounters'],
                'assets': asset_schema.dump(assets, many=True)[0],
            },
        }
        return rtn


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
                log.warning(f'_get_annotations failed {ex.message}')
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
                log.warning(f'EDM triggered self-deletion of {sighting} result={result}')
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
            log.warning(
                f'Sighting.delete {sighting.guid} failed: ({ex.status_code} / edm={edm_status_code}) {ex.message}'
            )
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


@api.route('/<uuid:sighting_guid>/sage_identified/<uuid:job_guid>')
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
            sighting.identified(job_guid, json.loads(request.data))
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
            sighting.stage = SightingStage.identification
            sighting.ia_pipeline()
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
