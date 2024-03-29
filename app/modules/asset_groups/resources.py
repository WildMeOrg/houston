# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Asset_groups resources
--------------------------
"""

import json
import logging
import uuid
from http import HTTPStatus

import werkzeug
from flask import request
from flask_login import current_user

import app.extensions.logging as AuditLog
from app.extensions import db
from app.extensions.api import Namespace, abort
from app.extensions.api.parameters import PaginationParameters
from app.modules.auth.utils import recaptcha_required
from app.modules.sightings.schemas import DetailedSightingSchema
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException
from flask_restx_patched import Resource

from . import parameters, schemas
from .metadata import AssetGroupMetadata, AssetGroupMetadataError
from .models import AssetGroup, AssetGroupSighting, AssetGroupSightingStage

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace(
    'asset_groups', description='Asset_groups'
)  # pylint: disable=invalid-name


# the resolve_object_by_model returns a tuple if the return_not_found is set as it is here
# a common helper to get the asset_group object or raise 428 if remote only
def _get_asset_group_with_428(asset_group):
    asset_group, asset_group_guids = asset_group
    if asset_group is not None:
        return asset_group

    # We did not find the asset_group by its UUID in the Houston database
    # We now need to check the GitlabManager for the existence of that repo
    asset_group_guid = asset_group_guids[0]
    assert isinstance(asset_group_guid, uuid.UUID)

    if AssetGroup.is_on_remote(asset_group_guid):
        # Asset_group is not local but is on remote
        log.info(f'Asset_group {asset_group_guid} on remote but not local')
        raise werkzeug.exceptions.PreconditionRequired
    else:
        # Asset_group neither local nor remote
        return None


@api.route('/')
class AssetGroups(Resource):
    """
    Manipulations with Asset_groups.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AssetGroup,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseAssetGroupSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Asset_group.
        """
        return AssetGroup.query_search(args=args)

    @recaptcha_required
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AssetGroup,
            'action': AccessOperation.WRITE,
        },
    )
    @api.parameters(parameters.CreateAssetGroupParameters())
    @api.response(schemas.DetailedAssetGroupSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Asset_group.
        """
        import app.extensions.logging as AuditLog  # NOQA
        from app.extensions.elapsed_time import ElapsedTime
        from app.modules.users.models import User

        timer = ElapsedTime()
        metadata = AssetGroupMetadata(json.loads(request.data))
        try:
            metadata.process_request()
        except AssetGroupMetadataError as error:
            abort(error.status_code, error.message)
        except Exception as ex:
            # Want to handle all other errors gracefully too
            abort(400, ex)

        if (
            metadata.anonymous
            and metadata.submitter_email is not None
            and metadata.anonymous_submitter is None
        ):
            metadata.anonymous_submitter = User.ensure_user(
                metadata.submitter_email, User.initial_random_password(), is_active=False
            )
            log.info(
                f'New inactive user created as submitter: {metadata.submitter_email}'
            )

        try:
            asset_group, _ = AssetGroup.create_from_metadata(metadata)
        except HoustonException as ex:
            log.warning(
                f'AssetGroup creation for transaction_id={metadata.tus_transaction_id} failed'
            )
            abort(ex.status_code, ex.message)
        except Exception as ex:
            abort(400, f'Creation failed {ex}')

        try:
            input_filenames = asset_group.begin_ia_pipeline(metadata)
        except HoustonException as ex:
            asset_group.delete()
            abort(
                ex.status_code,
                ex.message,
                sage_status_code=ex.get_val('sage_status_code', None),
            )
        except Exception as ex:
            asset_group.delete()
            # If this was already an abort, use the correct message
            message = ex.data if hasattr(ex, 'data') else ex
            abort(400, f'IA pipeline failed {message}')

        AuditLog.user_create_object(log, asset_group, duration=timer.elapsed())

        try:
            asset_group.git_commit_delay(input_filenames)
        except Exception as ex:
            asset_group.delete()
            # If this was already an abort, use the correct message
            message = ex.data if hasattr(ex, 'data') else str(ex)
            abort(400, f'Asset preparation failed {message}')
            raise

        db.session.refresh(asset_group)

        return asset_group


@api.route('/search')
@api.login_required(oauth_scopes=['asset_groups:read'])
class AssetGroupElasticsearch(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AssetGroup,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseAssetGroupSchema(many=True))
    @api.paginate()
    def get(self, args):
        search = {}
        args['total'] = True
        return AssetGroup.elasticsearch(search, **args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AssetGroup,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseAssetGroupSchema(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()

        args['total'] = True
        return AssetGroup.elasticsearch(search, **args)


@api.route('/<uuid:asset_group_guid>')
@api.resolve_object_by_model(AssetGroup, 'asset_group', return_not_found=True)
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset_group not found.',
)
@api.response(
    code=HTTPStatus.PRECONDITION_REQUIRED,
    description='Asset_group not local, need to post',
)
class AssetGroupByID(Resource):
    """
    Manipulations with a specific Asset_group.
    """

    @api.permission_required(
        permissions.ModuleOrObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AssetGroup,
            'obj': kwargs['asset_group'][0],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedAssetGroupSchema())
    def get(self, asset_group):
        """
        Get Asset_group details by ID.

        If asset_group is not found locally in database, but is on the remote Github,
        a 428 PRECONDITION_REQUIRED will be returned.

        If asset_group is not local and not on remote github, 404 will be returned.

        Otherwise the asset_group will be returned
        """
        asset_group = _get_asset_group_with_428(asset_group)
        if asset_group is None:
            raise werkzeug.exceptions.NotFound

        return asset_group

    @api.login_required(oauth_scopes=['asset_groups:write'])
    @api.permission_required(
        permissions.ModuleOrObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AssetGroup,
            'obj': kwargs['asset_group'][0],
            'action': AccessOperation.WRITE,
        },
    )
    @api.response(schemas.DetailedAssetGroupSchema())
    def post(self, asset_group):
        """
        Post Asset_group details by ID. (Actually a get with clone)

        If asset_group is not found locally in database, but is on the remote Github,
        it will be cloned from the remote github

        If asset_group is not local and not on remote github, 404 will be returned.

        Otherwise the asset_group will be returned
        """
        asset_group, asset_group_guids = asset_group
        if asset_group is not None:
            log.info(f'Asset_group {asset_group.guid} found locally on post')
            return asset_group

        # We did not find the asset_group by its UUID in the Houston database
        # We now need to check the GitlabManager for the existence of that repo
        asset_group_guid = asset_group_guids[0]
        assert isinstance(asset_group_guid, uuid.UUID)

        # Clone if present on gitlab
        asset_group = AssetGroup.ensure_store(asset_group_guid)
        if asset_group is None:
            # We have checked the asset_group manager and cannot find this asset_group, raise 404 manually
            raise werkzeug.exceptions.NotFound

        return asset_group

    @api.permission_required(
        permissions.ModuleOrObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AssetGroup,
            'obj': kwargs['asset_group'][0],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['asset_groups:write'])
    @api.parameters(parameters.PatchAssetGroupDetailsParameters())
    @api.response(schemas.DetailedAssetGroupSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, asset_group):
        """
        Patch Asset_group details by ID.

        If asset_group is not found locally in database, but is on the remote Github,
        a 428 PRECONDITION_REQUIRED will be returned.

        If asset_group is not local and not on remote github, 404 will be returned.

        Otherwise the asset_group will be patched
        """
        asset_group = _get_asset_group_with_428(asset_group)
        if asset_group is None:
            raise werkzeug.exceptions.NotFound

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Asset_group details.'
        )
        with context:
            parameters.PatchAssetGroupDetailsParameters.perform_patch(args, asset_group)
            db.session.merge(asset_group)
        return asset_group

    @api.permission_required(
        permissions.ModuleOrObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AssetGroup,
            'obj': kwargs['asset_group'][0],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['asset_groups:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, asset_group):
        """
        Delete an Asset_group by ID.
        """
        _, asset_group_id = asset_group
        asset_group = _get_asset_group_with_428(asset_group)

        if asset_group is not None:
            try:
                asset_group.delete()
            except HoustonException as ex:
                abort(ex.status_code, ex.message)
        else:
            from app.extensions.git_store.tasks import delete_remote

            delete_remote.delay(str(asset_group_id))

        return None


@api.login_required(oauth_scopes=['asset_groups:read'])
@api.route('/debug/<uuid:asset_group_guid>', doc=False)
@api.resolve_object_by_model(AssetGroup, 'asset_group', return_not_found=True)
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset_group not found.',
)
@api.response(
    code=HTTPStatus.PRECONDITION_REQUIRED,
    description='Asset_group not local, need to post',
)
class AssetGroupByIDDebug(Resource):
    """
    Manipulations with a specific Asset_group.
    """

    @api.permission_required(
        permissions.ModuleOrObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AssetGroup,
            'obj': kwargs['asset_group'][0],
            'action': AccessOperation.READ_DEBUG,
        },
    )
    @api.response(schemas.DebugAssetGroupSchema())
    def get(self, asset_group):
        """
        Get Asset_group details by ID.

        If asset_group is not found locally in database, but is on the remote Github,
        a 428 PRECONDITION_REQUIRED will be returned.

        If asset_group is not local and not on remote github, 404 will be returned.

        Otherwise the asset_group will be returned
        """
        asset_group = _get_asset_group_with_428(asset_group)
        if asset_group is None:
            raise werkzeug.exceptions.NotFound

        return asset_group


@api.login_required(oauth_scopes=['asset_groups:read'])
@api.route('/sighting')
class AssetGroupSightings(Resource):
    """
    Manipulations with Asset_group sightings.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AssetGroupSighting,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseAssetGroupSightingSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Asset_group Sightings.
        """
        return AssetGroupSighting.query_search(args=args)


@api.login_required(oauth_scopes=['asset_groups:read'])
@api.route('/sighting/pending/public')
class PublicPendingAssetGroupSightings(Resource):
    """
    Get the Public Pending Asset_group sightings.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AssetGroupSighting,
            'action': AccessOperation.READ_BY_ROLE,
        },
    )
    @api.response(schemas.BaseAssetGroupSightingSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Pending Public Asset_group Sightings for a researcher to process
        """
        from app.modules.users.models import User

        query = AssetGroupSighting.query_search(args=args)
        query = query.filter(
            AssetGroupSighting.stage != AssetGroupSightingStage.processed
        )

        if current_user.is_researcher:
            query = query.join(AssetGroup)
            query = query.join(AssetGroup.owner)
            query = query.filter(AssetGroup.owner_guid == User.get_public_user().guid)

            return query

        # deliberately return Nothing for non researchers
        return []


@api.login_required(oauth_scopes=['asset_groups:read'])
@api.route('/sighting/pending/contributor')
class ContributorPendingAssetGroupSightings(Resource):
    """
    Get the Contributor Pending Asset_group sightings.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AssetGroupSighting,
            'action': AccessOperation.READ_BY_ROLE,
        },
    )
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseAssetGroupSightingSchema(many=True))
    def get(self, args):
        """
        List of Pending Contributor submitted Asset_group Sightings for a researcher to process
        """

        query = AssetGroupSighting.query_search()
        query = query.filter(
            AssetGroupSighting.stage != AssetGroupSightingStage.processed
        )
        response = []
        if current_user.is_researcher:
            # TODO figure out if this is possible as an sqlalchemy query, as the roles are bitmaps, this may be hard
            for ags in query.all():
                if (
                    ags.asset_group.owner.is_contributor
                    and not ags.asset_group.owner.is_researcher
                ):
                    response.append(ags)
            # Manually apply offset and limit after the list is created
            offset = args['offset']
            limit = args['limit']
            return response[offset : offset + limit]
        return []


@api.route('/sighting/search')
@api.login_required(oauth_scopes=['asset_group_sightings:read'])
class AssetGroupSightingElasticsearch(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AssetGroupSighting,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseAssetGroupSightingSchema(many=True))
    @api.paginate()
    def get(self, args):
        search = {}
        args['total'] = True
        return AssetGroupSighting.elasticsearch(search, **args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': AssetGroupSighting,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseAssetGroupSightingSchema(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()

        args['total'] = True
        return AssetGroupSighting.elasticsearch(search, **args)


@api.route('/sighting/<uuid:asset_group_sighting_guid>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset_group_sighting not found.',
)
@api.resolve_object_by_model(AssetGroupSighting, 'asset_group_sighting')
class AssetGroupSightingByID(Resource):
    """
    The Asset Group Sighting may be read or patched as part of curation
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset_group_sighting'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedAssetGroupSightingSchema())
    def get(self, asset_group_sighting):
        """
        Get Asset_group_sighting details by ID.
        """
        return asset_group_sighting

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset_group_sighting'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['asset_group_sightings:write'])
    @api.parameters(parameters.PatchAssetGroupSightingDetailsParameters())
    @api.response(schemas.DetailedAssetGroupSightingSchema())
    def patch(self, args, asset_group_sighting):
        import app.extensions.logging as AuditLog  # NOQA
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()
        context = api.commit_or_abort(
            db.session,
            default_error_message='Failed to update Asset_group_sighting details.',
        )
        with context:
            try:
                parameters.PatchAssetGroupSightingDetailsParameters.perform_patch(
                    args, asset_group_sighting
                )
            except AssetGroupMetadataError as error:
                abort(error.status_code, error.message)

            db.session.merge(asset_group_sighting)
        AuditLog.patch_object(log, asset_group_sighting, args, duration=timer.elapsed())
        return asset_group_sighting


@api.route('/sighting/jobs/<uuid:asset_group_sighting_guid>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset_group_sighting not found.',
)
@api.resolve_object_by_model(AssetGroupSighting, 'asset_group_sighting')
class AssetGroupSightingJobsByID(Resource):
    """
    The Asset Group Sighting jobs details
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset_group_sighting'],
            'action': AccessOperation.READ_DEBUG,
        },
    )
    @api.login_required(oauth_scopes=['asset_group_sightings:read'])
    def get(self, asset_group_sighting):
        """
        Get Asset_group_sighting job details by ID.
        """
        return asset_group_sighting.get_jobs_debug(verbose=True)


@api.route('/sighting/debug/<uuid:asset_group_sighting_guid>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset_group_sighting not found.',
)
@api.resolve_object_by_model(AssetGroupSighting, 'asset_group_sighting')
class AssetGroupSightingDebugByID(Resource):
    """
    The Asset Group Sighting jobs details
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset_group_sighting'],
            'action': AccessOperation.READ_DEBUG,
        },
    )
    @api.login_required(oauth_scopes=['asset_group_sightings:read'])
    @api.response(schemas.DebugAssetGroupSightingSchema())
    def get(self, asset_group_sighting):
        """
        Get Asset_group_sighting debug details by ID.
        """
        return asset_group_sighting


@api.route('/sighting/as_sighting/<uuid:asset_group_sighting_guid>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset_group_sighting not found.',
)
@api.resolve_object_by_model(AssetGroupSighting, 'asset_group_sighting')
class AssetGroupSightingAsSighting(Resource):
    """
    The Asset Group Sighting may be read or patched as part of curation
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset_group_sighting'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.AssetGroupSightingAsSightingWithPipelineStatusSchema())
    @api.login_required(oauth_scopes=['asset_group_sightings:read'])
    def get(self, asset_group_sighting):
        """
        Get Asset_group_sighting details by ID. Note this uses a schema that
        formats the AGS like a standard sighting, which is done by pulling out
        config fields to the top-level json
        """
        return asset_group_sighting

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset_group_sighting'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['asset_group_sightings:write'])
    @api.parameters(parameters.PatchAssetGroupSightingAsSightingParameters())
    @api.response(schemas.AssetGroupSightingAsSightingSchema())
    def patch(self, args, asset_group_sighting):
        import app.extensions.logging as AuditLog  # NOQA
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        context = api.commit_or_abort(
            db.session,
            default_error_message='Failed to update Asset_group_sighting details.',
        )
        with context:
            try:
                parameters.PatchAssetGroupSightingDetailsParameters.perform_patch(
                    args, asset_group_sighting
                )
            except AssetGroupMetadataError as error:
                abort(error.status_code, error.message)
            db.session.merge(asset_group_sighting)
        AuditLog.patch_object(log, asset_group_sighting, args, duration=timer.elapsed())
        return asset_group_sighting

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset_group_sighting'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['asset_group_sightings:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, asset_group_sighting):
        """Delete an asset group sighting by ID."""
        asset_group = asset_group_sighting.asset_group
        if [asset_group_sighting] == asset_group.asset_group_sightings:
            # Delete the only asset group sighting deletes the asset group
            try:
                asset_group.delete()
            except HoustonException as ex:
                abort(ex.status_code, ex.message)
        else:
            asset_group.delete_asset_group_sighting(asset_group_sighting)


@api.route('/sighting/<uuid:asset_group_sighting_guid>/encounter/<uuid:encounter_guid>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset_group_sighting not found.',
)
@api.resolve_object_by_model(AssetGroupSighting, 'asset_group_sighting')
class AssetGroupSightingEncounterByID(Resource):
    """
    The config for the Encounter within the Asset Group Sighting may be patched as part of curation
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset_group_sighting'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['asset_group_sightings:write'])
    @api.parameters(parameters.PatchAssetGroupSightingEncounterDetailsParameters())
    @api.response(schemas.DetailedAssetGroupSightingSchema())
    def patch(self, args, asset_group_sighting, encounter_guid):
        import app.extensions.logging as AuditLog  # NOQA
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()
        context = api.commit_or_abort(
            db.session,
            default_error_message='Failed to update Asset_group_sighting details.',
        )
        with context:
            try:
                parameters.PatchAssetGroupSightingEncounterDetailsParameters.perform_patch(
                    args,
                    asset_group_sighting,
                    state={'encounter_uuid': encounter_guid},
                )
            except AssetGroupMetadataError as error:
                abort(error.status_code, error.message)
            db.session.merge(asset_group_sighting)
        AuditLog.patch_object(log, asset_group_sighting, args, duration=timer.elapsed())
        return asset_group_sighting


@api.route(
    '/sighting/as_sighting/<uuid:asset_group_sighting_guid>/encounter/<uuid:encounter_guid>'
)
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset_group_sighting not found.',
)
@api.resolve_object_by_model(AssetGroupSighting, 'asset_group_sighting')
class AssetGroupSightingAsSightingEncounterByID(Resource):
    """
    The config for the Encounter within the Asset Group Sighting may be patched as part of curation
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset_group_sighting'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['asset_group_sightings:write'])
    @api.parameters(parameters.PatchAssetGroupSightingEncounterDetailsParameters())
    def patch(self, args, asset_group_sighting, encounter_guid):
        import app.extensions.logging as AuditLog  # NOQA
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()
        context = api.commit_or_abort(
            db.session,
            default_error_message='Failed to update Asset_group_sighting details.',
        )
        with context:
            try:
                parameters.PatchAssetGroupSightingEncounterDetailsParameters.perform_patch(
                    args,
                    asset_group_sighting,
                    state={'encounter_uuid': encounter_guid},
                )
            except AssetGroupMetadataError as error:
                abort(error.status_code, error.message)
            db.session.merge(asset_group_sighting)
        AuditLog.patch_object(log, asset_group_sighting, args, duration=timer.elapsed())
        schema = schemas.AssetGroupSightingEncounterSchema()
        returned_json = {}
        houston_encounter_json = asset_group_sighting.get_encounter_json(encounter_guid)
        returned_json.update(schema.dump(houston_encounter_json).data)
        return returned_json


@api.route('/sighting/<uuid:asset_group_sighting_guid>/commit')
@api.login_required(oauth_scopes=['asset_group_sightings:write'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset_group_sighting not found.',
)
@api.resolve_object_by_model(AssetGroupSighting, 'asset_group_sighting')
class AssetGroupSightingCommit(Resource):
    """
    Commit the Asset Group Sighting
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset_group_sighting'],
            'action': AccessOperation.WRITE,
        },
    )
    # NOTE this returns a sighting schema not an AssetGroup one as the output of this is that
    # a sighting is created.
    @api.response(DetailedSightingSchema())
    def post(self, asset_group_sighting):
        try:
            sighting = asset_group_sighting.commit()
        except HoustonException as ex:
            abort(ex.status_code, ex.message, errorFields=ex.get_val('error', 'Error'))

        return sighting


@api.route('/sighting/<uuid:asset_group_sighting_guid>/detect')
@api.login_required(oauth_scopes=['asset_group_sightings:write'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset_group_sighting not found.',
)
@api.resolve_object_by_model(AssetGroupSighting, 'asset_group_sighting')
class AssetGroupSightingDetect(Resource):
    """
    Rerun detection on the Asset Group Sighting after changes made
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset_group_sighting'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.response(schemas.DetailedAssetGroupSightingSchema())
    def post(self, asset_group_sighting):
        try:
            asset_group_sighting.rerun_detection()
        except HoustonException as ex:
            abort(ex.status_code, ex.message, errorFields=ex.get_val('error', 'Error'))
        return asset_group_sighting


@api.route(
    '/sighting/<uuid:asset_group_sighting_guid>/sage_detected/<uuid:job_guid>', doc=False
)
@api.login_required(oauth_scopes=['asset_group_sightings:write'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset_group_sighting not found.',
)
@api.resolve_object_by_model(AssetGroupSighting, 'asset_group_sighting')
class AssetGroupSightingDetected(Resource):
    """
    Detection of Asset Group Sighting complete
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset_group_sighting'],
            'action': AccessOperation.WRITE_INTERNAL,
        },
    )
    def post(self, asset_group_sighting, job_guid):
        try:
            # Don't expect the response to have the full JSON response, leads to errors in Sage that can't be handled
            # asset_group_sighting.detected(job_guid, json.loads(request.data))

            # Instead, use the data we already have to fetch the result from Sage
            from .tasks import fetch_sage_detection_result

            promise = fetch_sage_detection_result.delay(
                str(asset_group_sighting.guid), str(job_guid)
            )
            log.info(
                f'Fetching Detection for Asset Group Sighting:{asset_group_sighting.guid} in celery'
            )
            return str(promise.id)
        except HoustonException as ex:
            message = f'sage_detected error: {request.data}'
            AuditLog.audit_log_object_error(log, asset_group_sighting, message)
            log.exception(message)
            abort(ex.status_code, ex.message, errorFields=ex.get_val('error', 'Error'))


@api.route('/tus/collect/<uuid:asset_group_guid>')
@api.login_required(oauth_scopes=['asset_groups:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset_group not found.',
)
@api.resolve_object_by_model(AssetGroup, 'asset_group', return_not_found=True)
class AssetGroupTusCollect(Resource):
    """
    Collect files uploaded by Tus endpoint for this Asset_group
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset_group'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedAssetGroupSchema())
    def get(self, asset_group):
        asset_group, asset_group_guids = asset_group

        if asset_group is None:
            # We have checked the asset_group manager and cannot find this asset_group, raise 404 manually
            raise werkzeug.exceptions.NotFound

        asset_group.import_tus_files()

        return asset_group
