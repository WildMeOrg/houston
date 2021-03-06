# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API FileUploads resources
--------------------------
"""

import logging

from flask_login import current_user  # NOQA
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus

from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation


from . import parameters, schemas
from .models import FileUpload


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('fileuploads', description='FileUploads')  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['fileuploads:read'])
class FileUploads(Resource):
    """
    Manipulations with FileUploads.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': FileUpload,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseFileUploadSchema(many=True))
    def get(self, args):
        """
        List of FileUpload.

        Returns a list of FileUpload starting from ``offset`` limited by ``limit``
        parameter.
        """
        return FileUpload.query.offset(args['offset']).limit(args['limit'])

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': FileUpload,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['fileuploads:write'])
    @api.parameters(parameters.CreateFileUploadParameters())
    @api.response(schemas.DetailedFileUploadSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of FileUpload.
        """
        # TODO potentially handle non-json `<form method="post" enctype="multipart/form-data">` input?
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new FileUpload'
        )
        return
        with context:
            args['owner_guid'] = current_user.guid
            fileupload = FileUpload(**args)
            # User who creates the org gets added to it as a member and a moderator
            fileupload.add_user_in_context(current_user)
            fileupload.add_moderator_in_context(current_user)
            db.session.add(fileupload)
        return fileupload


@api.route('/<uuid:fileupload_guid>')
@api.login_required(oauth_scopes=['fileuploads:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='FileUpload not found.',
)
@api.resolve_object_by_model(FileUpload, 'fileupload')
class FileUploadByID(Resource):
    """
    Manipulations with a specific FileUpload.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['fileupload'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedFileUploadSchema())
    def get(self, fileupload):
        """
        Get FileUpload details by ID.
        """
        return fileupload

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['fileupload'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['fileuploads:write'])
    # @api.parameters(parameters.PatchFileUploadDetailsParameters())
    @api.response(schemas.DetailedFileUploadSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, fileupload):
        """
        Patch FileUpload details by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update FileUpload details.'
        )
        with context:
            parameters.PatchFileUploadDetailsParameters.perform_patch(
                args, obj=fileupload
            )
            db.session.merge(fileupload)
        return fileupload

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['fileupload'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['fileuploads:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, fileupload):
        """
        Delete a FileUpload by ID.
        """
        fileupload.delete()
        return None
