# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Assets resources
--------------------------
"""

import logging

from flask import send_file

from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus
from app.extensions import db
from app.extensions.api import Namespace
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.extensions.api.parameters import PaginationParameters
import werkzeug

from .models import Asset

from . import schemas, parameters


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('assets', description='Assets')  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['assets:read'])
class Assets(Resource):
    """
    Manipulations with Assets.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Asset,
            'action': AccessOperation.READ,
        },
    )
    @api.login_required(oauth_scopes=['assets:read'])
    @api.response(schemas.BaseAssetSchema(many=True))
    @api.parameters(PaginationParameters())
    def get(self, args):
        """
        List of Assets.

        Returns a list of Asset starting from ``offset`` limited by ``limit``
        parameter.
        """
        return (
            Asset.query.order_by(Asset.guid).offset(args['offset']).limit(args['limit'])
        )

    # @api.permission_required(
    #     permissions.ModuleAccessPermission,
    #     kwargs_on_request=lambda kwargs: {
    #         'module': Asset,
    #         'action': AccessOperation.WRITE,
    #     },
    # )
    @api.login_required(oauth_scopes=['assets:write'])
    @api.parameters(parameters.PatchAssetParameters())
    @api.response(schemas.BaseAssetSchema(many=True))
    def patch(self, args):
        """
        Patch Assets' details by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to bulk update Asset details.'
        )
        with context:
            assets = parameters.PatchAssetParameters.perform_patch(args, obj_cls=Asset)
            for asset in assets:
                db.session.merge(asset)
        return assets


@api.route('/<uuid:asset_guid>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset not found.',
)
@api.resolve_object_by_model(Asset, 'asset')
class AssetByID(Resource):
    """
    Manipulations with a specific Asset.
    """

    @api.login_required(oauth_scopes=['assets:read'])
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedAssetSchema())
    def get(self, asset):
        """
        Get Asset details by ID.
        """
        return asset

    @api.login_required(oauth_scopes=['assets:write'])
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.parameters(parameters.PatchAssetParameters())
    @api.response(schemas.DetailedAssetSchema())
    def patch(self, args, asset):
        """
        Patch Asset details by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Asset details.'
        )
        with context:
            parameters.PatchAssetParameters.perform_patch(args, asset)
            db.session.merge(asset)
        return asset


@api.route('/src/<uuid:asset_guid>', defaults={'format': 'master'}, doc=False)
@api.route('/src/<string:format>/<uuid:asset_guid>')
@api.login_required(oauth_scopes=['assets:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset not found.',
)
@api.resolve_object_by_model(Asset, 'asset')
class AssetSrcUByID(Resource):
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset'],
            'action': AccessOperation.READ,
        },
    )
    def get(self, asset, format):
        cls = type(asset.git_store)
        cls.ensure_store(asset.git_store_guid)

        try:
            asset_format_path = asset.get_or_make_format_path(format)
        except Exception:
            logging.exception('Got exception from get_or_make_format_path()')
            raise werkzeug.exceptions.NotImplemented
        return send_file(asset_format_path, asset.DERIVED_MIME_TYPE)


@api.route('/src_raw/<uuid:asset_guid>', doc=False)
@api.login_required(oauth_scopes=['assets:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset not found.',
)
@api.resolve_object_by_model(Asset, 'asset')
class AssetSrcRawByID(Resource):
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset'],
            'action': AccessOperation.READ_PRIVILEGED,
        },
    )
    def get(self, asset):
        log.info(f'Sage raw src read of Asset {asset.guid}')
        return send_file(asset.get_symlink())


@api.route('/jobs/<uuid:asset_guid>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Asset not found.',
)
@api.resolve_object_by_model(Asset, 'asset')
class AssetJobsByID(Resource):
    """
    Manipulations with a specific Asset.
    """

    @api.login_required(oauth_scopes=['assets:read'])
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['asset'],
            'action': AccessOperation.READ_DEBUG,
        },
    )
    def get(self, asset):
        """
        Get Asset job details by ID.
        """
        return asset.get_jobs_debug(verbose=True)
