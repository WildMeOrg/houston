# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods
"""
RESTful API User resources
--------------------------
"""

import logging

from flask_login import current_user
from flask_restplus_patched import Resource
from flask_restplus._http import HTTPStatus
from app.extensions.api import abort

from app.extensions.api import Namespace

from . import permissions, schemas, parameters
from .models import db, User


log = logging.getLogger(__name__)
api = Namespace('users', description='Users')


@api.route('/')
class Users(Resource):
    """
    Manipulations with users.
    """

    @api.login_required(oauth_scopes=['users:read'])
    @api.permission_required(permissions.StaffRolePermission())
    @api.response(schemas.BaseUserSchema(many=True))
    @api.paginate(parameters.ListUserParameters())
    def get(self, args):
        """
        List of users.

        Returns a list of users starting from ``offset`` limited by ``limit``
        parameter.
        """
        search = args.get('search', None)
        if search is not None and len(search) == 0:
            search = None

        users = User.query_search(search)

        return users.order_by(User.guid)

    @api.parameters(parameters.CreateUserParameters())
    @api.response(schemas.DetailedUserSchema())
    @api.response(code=HTTPStatus.FORBIDDEN)
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.BAD_REQUEST)
    @api.doc(id='create_user')
    def post(self, args):
        """
        Create a new user.
        """
        email = args.get('email', None)
        user = User.query.filter_by(email=email).first()

        if user is not None:
            abort(
                code=HTTPStatus.CONFLICT, message='The email address is already in use.'
            )

        if 'password' not in args:
            abort(code=HTTPStatus.BAD_REQUEST, message='Must provide a password')

        args['is_active'] = True

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new user.'
        )
        with context:
            new_user = User(**args)
            db.session.add(new_user)
        db.session.refresh(new_user)

        return new_user

    @api.login_required(oauth_scopes=['users:write'])
    @api.permission_required(permissions.AdminRolePermission())
    @api.parameters(parameters.DeleteUserParameters())
    def delete(self, args):
        """
        Remove a member.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to delete user.'
        )
        with context:
            user_guid = args['user_guid']
            user = User.query.filter_by(id=user_guid).first_or_404()
            db.session.delete(user)

        return None


@api.route('/<uuid:user_guid>')
@api.login_required(oauth_scopes=['users:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='User not found.',
)
@api.resolve_object_by_model(User, 'user')
class UserByID(Resource):
    """
    Manipulations with a specific user.
    """

    @api.permission_required(
        permissions.OwnerRolePermission,
        kwargs_on_request=lambda kwargs: {'obj': kwargs['user']},
    )
    @api.response(schemas.DetailedUserSchema())
    def get(self, user):
        """
        Get user details by ID.
        """
        return user

    @api.login_required(oauth_scopes=['users:write'])
    @api.permission_required(
        permissions.OwnerModifyRolePermission,
        kwargs_on_request=lambda kwargs: {'obj': kwargs['user']},
    )
    @api.permission_required(permissions.WriteAccessPermission())
    @api.parameters(parameters.PatchUserDetailsParameters())
    @api.response(schemas.DetailedUserSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, user):
        """
        Patch user details by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update user details.'
        )
        with context:
            parameters.PatchUserDetailsParameters.perform_patch(args, user)
            db.session.merge(user)
        db.session.refresh(user)

        return user


@api.route('/me')
@api.login_required(oauth_scopes=['users:read'])
class UserMe(Resource):
    """
    Useful reference to the authenticated user itself.
    """

    @api.response(schemas.PersonalUserSchema())
    def get(self):
        """
        Get current user details.
        """
        return User.query.get_or_404(current_user.guid)


@api.route('/admin_user_initialized')
class AdminUserInitialized(Resource):
    def get(self):
        """
        Checks if admin user exists and returns bool
        """
        admin_initialized = User.admin_user_initialized()
        return {'initialized': admin_initialized}

    @api.parameters(parameters.AdminUserInitializedParameters())
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.METHOD_NOT_ALLOWED)
    def post(self, args):
        """
        Creates initial startup admin if none exists.

        CommandLine:
            curl \
                -X GET \
                http://127.0.0.1:5000/api/v1/users/admin_user_initialized | jq

            EMAIL='test@wildme.org'
            PASSWORD='test'
            curl \
                -X POST \
                -H 'Content-Type: multipart/form-data' \
                -H 'Accept: application/json' \
                -F email=${EMAIL} \
                -F password=${PASSWORD} \
                http://127.0.0.1:5000/api/v1/users/admin_user_initialized | jq

            curl \
                -X POST \
                -H 'Content-Type: application/json' \
                -d '{"password":"hello", "email":"bob@bob.com"}' \
                http://127.0.0.1:5000/api/v1/users/admin_user_initialized | jq
        """
        if User.admin_user_initialized():
            log.warning(
                'First-run admin user creation was attempted but an admin already exists.'
            )
            abort(
                code=HTTPStatus.METHOD_NOT_ALLOWED,
                message='Disabled because the initial startup admin already exists.',
            )
        else:
            email = args.get('email', None)
            password = args.get('password', None)
            admin = User.ensure_user(
                email,
                password,
                is_admin=True,
                update=True,
            )
            log.info('Success creating startup admin user via API: %r.' % (admin,))

        return {'initialized': True}


@api.route('/edm/sync')
# @api.login_required(oauth_scopes=['users:read'])
class UserEDMSync(Resource):
    """
    Useful reference to the authenticated user itself.
    """

    # @api.response(schemas.DetailedUserSchema())
    def get(self, refresh=False):
        """
        Get current user details.
        """
        edm_users, new_users, updated_users, failed_users = User.edm_sync_users(
            refresh=refresh
        )

        response = {
            'local': User.query.count(),
            'remote': len(edm_users),
            'added': len(new_users),
            'updated': len(updated_users),
            'failed': len(failed_users),
        }

        return response
