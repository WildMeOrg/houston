# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods
"""
RESTful API User resources
--------------------------
"""

import logging

from flask_login import current_user
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus
from app.extensions.api import abort
from app.extensions.api.parameters import PaginationParameters
from flask import current_app
from app.extensions.api import Namespace

from . import permissions, schemas, parameters
from app.modules.users.permissions.types import AccessOperation
from .models import db, User
import app.extensions.logging as AuditLog


log = logging.getLogger(__name__)
api = Namespace('users', description='Users')


@api.route('/')
class Users(Resource):
    """
    Manipulations with users.
    """

    @api.login_required(oauth_scopes=['users:read'])
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': User,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.UserListSchema(many=True))
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

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': User,
            'action': AccessOperation.WRITE,
        },
    )
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
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        email = args.get('email', None)
        user = User.query.filter_by(email=email).first()
        roles = args.pop('roles', [])
        if roles and (
            current_user.is_anonymous
            or not (
                current_user.is_privileged
                or current_user.is_admin
                or current_user.is_user_manager
            )
        ):
            abort(
                code=HTTPStatus.FORBIDDEN,
                message='You must be an admin, user manager or privileged to set roles for a new user',
            )
        for role in roles:
            args[role] = True

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

        deactivated_user = User.get_deactivated_account(email)
        if deactivated_user:
            if current_user.is_anonymous:
                # Need privileged user to restore
                abort(
                    code=HTTPStatus.CONFLICT,
                    message='The email address is already in use in an inactivated user.',
                )
            else:
                kwargs = {'email': email, 'password': args['password'], 'is_active': True}
                for role in roles:
                    kwargs[role] = True
                deactivated_user.email = email
                new_user = User.ensure_user(**kwargs, update=True)
        else:

            with context:
                new_user = User(**args)
                db.session.add(new_user)
            db.session.refresh(new_user)
            AuditLog.user_create_object(
                log, new_user, msg=f'{new_user.email}', duration=timer.elapsed()
            )
        return new_user


@api.route('/<uuid:user_guid>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='User not found.',
)
@api.resolve_object_by_model(User, 'user')
class UserByID(Resource):
    """
    Manipulations with a specific user.
    """

    # no decorators here for permissions or schemas, as getting specific user data is "public"
    #   with the schema being determined based on privileges below
    def get(self, user):
        """
        Get user details by ID.
        """
        from app.modules.users.permissions import rules
        from app.modules.users.schemas import DetailedUserSchema, PublicUserSchema

        if not current_user.is_anonymous and (
            rules.owner_or_privileged(current_user, user) or current_user.is_user_manager
        ):
            schema = DetailedUserSchema()
        else:
            schema = PublicUserSchema()
        return schema.dump(user)

    @api.login_required(oauth_scopes=['users:write'])
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['user'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.parameters(parameters.PatchUserDetailsParameters())
    @api.response(schemas.DetailedUserSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, user):
        """
        Patch user details by ID.
        """
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update user details.'
        )
        with context:
            parameters.PatchUserDetailsParameters.perform_patch(args, user)
            db.session.merge(user)
        db.session.refresh(user)
        AuditLog.patch_object(log, user, args, duration=timer.elapsed())
        return user

    @api.login_required(oauth_scopes=['users:write'])
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['user'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, user):
        """
        User is never deleted, only ever deactivated
        """
        user.deactivate()
        return None


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
                is_internal=True,
                is_admin=True,
                is_staff=True,
                is_researcher=True,
                is_contributor=True,
                is_user_manager=True,
                is_exporter=True,
                is_active=True,
                in_beta=True,
                in_alpha=True,
                update=True,
            )
            log.info(
                'Success creating startup (houston) admin user via API: %r.' % (admin,)
            )
            rtn = {'initialized': True}

            # now we attempt to create on edm as well
            from flask import current_app

            try:
                rtn['edmInitialized'] = current_app.edm.initialize_edm_admin_user(
                    email, password
                )
            except AttributeError:
                rtn['edmInitialized'] = False

            if not rtn['edmInitialized']:
                log.warning('EDM admin user not created; previous may have existed.')
            return rtn


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


@api.route('/<uuid:user_guid>/sightings')
@api.resolve_object_by_model(User, 'user')
class UserSightings(Resource):
    """
    EDM Sightings for a given Houston user. Note that we use PaginationParameters,
    meaning by default this call returns 20 sightings and will never return more
    than 100. For such scenarios the frontend should call this successively,
    allowing batches of <= 100 sightings to load while others are fetched.
    """

    @api.login_required(oauth_scopes=['users:read'])
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['user'],
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    def get(self, args, user):
        """
        Get Sightings for user with EDM metadata
        """
        response = {'sightings': [], 'success': True}

        start, end = args['offset'], args['offset'] + args['limit']
        for sighting in user.get_sightings()[start:end]:
            try:
                sighting_response = current_app.edm.get_dict(
                    'sighting.data_complete', sighting.guid
                )
            except AttributeError:
                response['success'] = False

            if (
                sighting_response is not None
                and sighting_response.get('result') is not None
            ):
                response['sightings'].append(sighting_response['result'])

        return response
