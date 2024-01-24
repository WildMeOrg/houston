# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Keywords resources
--------------------------
"""

import logging
from http import HTTPStatus

from app.extensions import db
from app.extensions.api import Namespace
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from flask_restx_patched import Resource

from . import parameters, schemas
from .models import Keyword

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('keywords', description='Keywords')  # pylint: disable=invalid-name


@api.route('/')
# no login decorator as read-all is public
class Keywords(Resource):
    """
    Manipulations with Keywords.
    """

    @api.response(schemas.DetailedKeywordSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Keyword.
        """
        return Keyword.query_search(args=args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Keyword,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['keywords:write'])
    @api.parameters(parameters.CreateKeywordParameters())
    @api.response(schemas.DetailedKeywordSchema())
    @api.response(code=HTTPStatus.BAD_REQUEST)
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Keyword.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Keyword'
        )
        with context:
            keyword = Keyword(**args)
            db.session.add(keyword)
        return keyword


@api.route('/<uuid:keyword_guid>')
@api.login_required(oauth_scopes=['keywords:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Keyword not found.',
)
@api.resolve_object_by_model(Keyword, 'keyword')
class KeywordByID(Resource):
    """
    Manipulations with a specific Keyword.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['keyword'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedKeywordSchema())
    def get(self, keyword):
        """
        Get Keyword details by ID.
        """
        return keyword

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['keyword'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['keywords:write'])
    @api.parameters(parameters.PatchKeywordDetailsParameters())
    @api.response(schemas.DetailedKeywordSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, keyword):
        """
        Patch Keyword details by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Keyword details.'
        )
        with context:
            parameters.PatchKeywordDetailsParameters.perform_patch(args, keyword)
            db.session.merge(keyword)
        return keyword

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['keyword'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['keywords:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, keyword):
        """
        Delete a Keyword by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to delete the Keyword.'
        )
        with context:
            db.session.delete(keyword)
        return None
