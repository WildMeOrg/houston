# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Asset_groups resources
--------------------------
"""

import logging
import werkzeug
import uuid

from flask import request, current_app
from flask_login import current_user
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus

from app.extensions import db
from app.extensions.api import Namespace, abort
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation

from . import parameters, schemas
from .metadata import AssetGroupMetadataError, CreateAssetGroupMetadata
from .models import (
    AssetGroup,
    AssetGroupSighting,
    AssetGroupSightingStage,
)
from app.modules.sightings.schemas import BaseSightingSchema

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace(
    'asset_groups', description='Asset_groups'
)  # pylint: disable=invalid-name


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
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseAssetGroupSchema(many=True))
    def get(self, args):
        """
        List of Asset_group.

        Returns a list of Asset_group starting from ``offset`` limited by ``limit``
        parameter.
        """
        return AssetGroup.query.offset(args['offset']).limit(args['limit'])

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
        from app.extensions.elapsed_time import ElapsedTime
        from app.modules.users.models import User
        import json

        timer = ElapsedTime()
        metadata = CreateAssetGroupMetadata(json.loads(request.data))
        try:
            metadata.process_request()
        except AssetGroupMetadataError as error:
            abort(
                success=False,
                passed_message=error.message,
                code=error.status_code,
            )

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

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Asset_group'
        )
        with context:
            args['owner_guid'] = metadata.owner.guid
            asset_group = AssetGroup.create_from_tus(
                metadata.description,
                metadata.owner,
                metadata.tus_transaction_id,
                metadata.files,
                metadata.anonymous_submitter,
            )

        asset_group.begin_ia_pipeline(metadata)
        log.info(
            f'AssetGroup {asset_group.guid}:"{metadata.description}" created by {metadata.owner.email} in {timer.elapsed()} seconds'
        )
        return asset_group


@api.route('/streamlined')
@api.login_required(oauth_scopes=['asset_groups:write'])
class AssetGroupsStreamlined(Resource):
    """
    Manipulations with Asset_groups + File add/commit.
    """

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
        r"""
        Create a new instance of Asset_group.

        CommandLine:
            EMAIL='test@localhost'
            PASSWORD='test'
            TIMESTAMP=$(date '+%Y%m%d-%H%M%S%Z')
            curl \
                -X POST \
                -c cookie.jar \
                -F email=${EMAIL} \
                -F password=${PASSWORD} \
                https://houston.dyn.wildme.io/api/v1/auth/sessions | jq
            curl \
                -X GET \
                -b cookie.jar \
                https://houston.dyn.wildme.io/api/v1/users/me | jq
            curl \
                -X POST \
                -b cookie.jar \
                -F description="This is a test asset_group (via CURL), please ignore" \
                -F files="@tests/asset_groups/test-000/zebra.jpg" \
                -F files="@tests/asset_groups/test-000/fluke.jpg" \
                https://houston.dyn.wildme.io/api/v1/asset_groups/streamlined | jq
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Asset_group'
        )
        with context:
            args['owner_guid'] = current_user.guid
            asset_group = AssetGroup(**args)
            db.session.add(asset_group)

        # Get the repo to make sure it's configured
        asset_group.ensure_repository()

        for upload_file in request.files.getlist('files'):
            asset_group.git_write_upload_file(upload_file)

        asset_group.git_commit('Initial commit via %s' % (request.url_rule,))

        asset_group.git_push()

        return asset_group


@api.login_required(oauth_scopes=['asset_groups:read'])
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

    # the resolve_object_by_model returns a tuple if the return_not_found is set as it is here
    # a common helper to get the asset_group object or raise 428 if remote only
    def _get_asset_group_with_428(self, asset_group):
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
        asset_group = self._get_asset_group_with_428(asset_group)
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
        asset_group = AssetGroup.ensure_asset_group(asset_group_guid)
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
        asset_group = self._get_asset_group_with_428(asset_group)
        if asset_group is None:
            raise werkzeug.exceptions.NotFound

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Asset_group details.'
        )
        with context:
            parameters.PatchAssetGroupDetailsParameters.perform_patch(
                args, obj=asset_group
            )
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
        asset_group = self._get_asset_group_with_428(asset_group)

        if asset_group is not None:
            asset_group.delete()

        return None


@api.route('/<uuid:asset_group_guid>/<uuid:asset_group_sighting_guid>/commit')
@api.login_required(oauth_scopes=['asset_groups:write'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset_group not found.',
)
@api.resolve_object_by_model(AssetGroup, 'asset_group')
@api.resolve_object_by_model(AssetGroupSighting, 'asset_group_sighting')
class AssetGroupSightingCommit(Resource):
    """
    Commit the Asset Group Sighting
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset_group'],
            'action': AccessOperation.WRITE,
        },
    )
    # NOTE this returns a sighting schema not an AssetGroup one as the output of this is that
    # a sighting is created
    @api.response(BaseSightingSchema())
    def post(self, asset_group, asset_group_sighting):
        from app.modules.utils import Cleanup
        from app.modules.sightings.models import Sighting
        from app.modules.encounters.models import Encounter

        if asset_group_sighting not in asset_group.sightings:
            abort(
                HTTPStatus.BAD_REQUEST,
                f'AssetGroupSighting {asset_group_sighting.guid} not in AssetGroup {asset_group.guid}',
            )
        if asset_group_sighting.stage != AssetGroupSightingStage.curation:
            abort(
                HTTPStatus.BAD_REQUEST,
                'AssetGroupSighting %s is currently %s, not curating cannot commit'
                % (asset_group_sighting.guid, asset_group_sighting.stage),
            )

        request_data = asset_group_sighting.meta
        if not request_data:
            abort(
                HTTPStatus.BAD_REQUEST,
                f'AssetGroupSighting {asset_group_sighting.guid} has no metadata',
            )

        # Create sighting in EDM
        result_data, message, error = current_app.edm.request_passthrough_result(
            'sighting.data', 'post', {'data': request_data}, ''
        )

        if not result_data:
            abort(HTTPStatus.BAD_REQUEST, message, errorFields=error)

        cleanup = Cleanup('AssetGroup')
        cleanup.add_guid(result_data['id'], Sighting)

        # if we get here, edm has made the sighting.  now we have to consider encounters contained within,
        # and make houston for the sighting + encounters

        # encounters via request_data and edm (result_data) need to have same count!
        if ('encounters' in request_data and 'encounters' not in result_data) or (
            'encounters' not in request_data and 'encounters' in result_data
        ):
            cleanup.rollback_and_abort(
                'Missing encounters between request_data and result',
                'Sighting.post missing encounters in one of %r or %r'
                % (request_data, result_data),
            )
        if not len(request_data['encounters']) == len(result_data['encounters']):
            cleanup.rollback_and_abort(
                'Imbalance in encounters between data and result',
                'Sighting.post imbalanced encounters in %r or %r'
                % (request_data, result_data),
            )

        sighting = Sighting(
            guid=result_data['id'],
            version=result_data.get('version', 2),
        )

        # Add the assets for all of the encounters to the created sighting object
        # TODO removed until the delete side of it works
        # for encounter in request_data['encounters']:
        #     for reference in encounter['assetReferences']:
        #         asset = asset_group.get_asset_for_file(reference)
        #         assert asset
        #         sighting.add_asset(asset)

        cleanup.add_object(sighting)

        for encounter_num in range(len(request_data['encounters'])):
            req_data = request_data['encounters'][encounter_num]
            res_data = result_data['encounters'][encounter_num]
            try:
                new_encounter = Encounter(
                    guid=res_data['id'],
                    version=res_data.get('version', 2),
                    owner_guid=asset_group.owner_guid,
                    submitter_guid=asset_group.submitter_guid,
                    public=asset_group.anonymous,
                )
                # TODO, we now have an encounter, add the appropriate annotations to it
                sighting.add_encounter(new_encounter)

            except Exception as ex:
                cleanup.rollback_and_abort(
                    'Problem with creating encounter: ',
                    f'{ex} on encounter {encounter_num}: enc={req_data}',
                )

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to persist new houston Sighting'
        )
        with context:
            db.session.add(sighting)
            for encounter in sighting.get_encounters():
                db.session.add(encounter)

        # AssetGroupSighting is finished, all subsequent processing is on the Sighting
        asset_group_sighting.delete()

        return sighting


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
