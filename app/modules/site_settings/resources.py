# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Site Settings resources
--------------------------
"""

import logging
from pathlib import Path

from flask import redirect, url_for
from flask_restx_patched import Resource
from flask_restx._http import HTTPStatus

from app.extensions import db
from app.extensions.api import abort, Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.fileuploads.models import FileUpload
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation

from . import schemas, parameters
from .models import SiteSetting


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace(
    'site-settings', description='Site Settings'
)  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['site-settings:read'])
class SiteSettings(Resource):
    """
    Manipulations with Site Settings.
    """

    @api.permission_required(permissions.AdminRolePermission())
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseSiteSettingSchema(many=True))
    def get(self, args):
        """
        List of SiteSetting.

        Returns a list of SiteSetting starting from ``offset`` limited by ``limit``
        parameter.
        """
        return (
            SiteSetting.query.order_by('key').offset(args['offset']).limit(args['limit'])
        )

    @api.permission_required(permissions.AdminRolePermission())
    @api.login_required(oauth_scopes=['site-settings:write'])
    @api.parameters(parameters.CreateSiteSettingParameters())
    @api.response(schemas.DetailedSiteSettingSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create or update a SiteSetting.
        """
        if args.get('transactionId'):
            transaction_id = args.pop('transactionId')
            if args.get('transactionPath'):
                paths = [args.pop('transactionPath')]
            else:
                paths = None
            fups = (
                FileUpload.create_fileuploads_from_tus(transaction_id, paths=paths) or []
            )
            if len(fups) != 1:
                # Delete the files in the filesystem
                # Can't use .delete() because fups are not persisted
                for fup in fups:
                    path = Path(fup.get_absolute_path())
                    if path.exists():
                        path.unlink()

                abort(
                    code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    message=f'Transaction {transaction_id} has {len(fups)} files, need exactly 1.',
                )
            with db.session.begin():
                db.session.add(fups[0])
            args['file_upload_guid'] = fups[0].guid
        site_setting = SiteSetting.set(**args)
        return site_setting


@api.route('/<string:site_setting_key>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='SiteSetting not found.',
)
@api.resolve_object_by_model(SiteSetting, 'site_setting', 'site_setting_key')
class SiteSettingByKey(Resource):
    """
    Manipulations with a specific SiteSetting.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['site_setting'],
            'action': AccessOperation.READ,
        },
    )
    def get(self, site_setting):
        """
        Get SiteSetting details by ID.
        """
        return redirect(
            url_for(
                'api.fileuploads_file_upload_src_u_by_id_2',
                fileupload_guid=site_setting.file_upload_guid,
            )
        )

    @api.permission_required(permissions.AdminRolePermission())
    @api.login_required(oauth_scopes=['site-settings:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, site_setting):
        """
        Delete a SiteSetting by ID.
        """
        context = api.commit_or_abort(
            db.session,
            default_error_message=f'Failed to delete the SiteSetting "{site_setting.key}".',
        )
        with context:
            db.session.delete(site_setting)
        return None
