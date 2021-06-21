# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Asset_groups resources
--------------------------
"""

import logging
import werkzeug
import uuid
import json

from flask import request
from flask_login import current_user
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus

from app.extensions import db
from app.extensions.api import Namespace, abort
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException

from . import parameters, schemas
from .metadata import (
    AssetGroupMetadataError,
    CreateAssetGroupMetadata,
    PatchAssetGroupSightingMetadata,
)
from .models import AssetGroup, AssetGroupSighting
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

        timer = ElapsedTime()
        metadata = CreateAssetGroupMetadata(json.loads(request.data))
        try:
            metadata.process_request()
        except AssetGroupMetadataError as error:
            abort(error.status_code, error.message)

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
            asset_group = AssetGroup.create_from_metadata(metadata)
        except HoustonException as ex:
            log.warning(
                f'AssetGroup creation for transaction_id={metadata.tus_transaction_id} failed'
            )
            abort(ex.status_code, ex.message)
        except Exception as ex:
            abort(400, f'Creation failed {ex}')

        try:
            asset_group.begin_ia_pipeline(metadata)
        except HoustonException as ex:
            asset_group.delete()
            abort(
                ex.status_code,
                ex.message,
                acm_status_code=ex.get_val('acm_status_code', None),
            )
        except Exception as ex:
            asset_group.delete()
            abort(400, f'IA pipeline failed {ex}')

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
        from .tasks import git_push

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

        # Do git push to gitlab in the background (we won't wait for its
        # completion here)
        git_push.delay(str(asset_group.guid))

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
    @api.login_required(oauth_scopes=['asset_group_sightings:read'])
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
        patchData = PatchAssetGroupSightingMetadata(json.loads(request.data))
        try:
            patchData.process_request(asset_group_sighting)
        except AssetGroupMetadataError as error:
            abort(
                passed_message=error.message,
                code=error.status_code,
            )
        context = api.commit_or_abort(
            db.session,
            default_error_message='Failed to update Asset_group_sighting details.',
        )
        with context:
            parameters.PatchAssetGroupSightingDetailsParameters.perform_patch(
                args, obj=asset_group_sighting
            )
            db.session.merge(asset_group_sighting)
        return asset_group_sighting


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
    # a sighting is created
    @api.response(BaseSightingSchema())
    def post(self, asset_group_sighting):
        try:
            sighting = asset_group_sighting.commit()
        except HoustonException as ex:
            abort(ex.status_code, ex.message, errorFields=ex.get_val('error', 'Error'))

        return sighting


@api.route('/sighting/<uuid:asset_group_sighting_guid>/sage_detected/<uuid:job_guid>')
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
            'action': AccessOperation.WRITE_PRIVILEGED,
        },
    )
    def post(self, asset_group_sighting, job_guid):
        try:
            asset_group_sighting.detected(job_guid, json.loads(request.data))
        except HoustonException as ex:
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
