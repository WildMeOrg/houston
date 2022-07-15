# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods
"""
RESTful API User resources
--------------------------
"""
import json
import logging

from flask import current_app, redirect, request, send_file, session, url_for
from flask_login import current_user

import app.extensions.logging as AuditLog
from app.extensions import is_extension_enabled
from app.extensions.api import Namespace, abort
from app.extensions.api.parameters import (
    PaginationParameters,
    PaginationParametersLatestFirst,
)
from app.extensions.email import Email
from app.modules import is_module_enabled
from app.modules.users.permissions.types import AccessOperation
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus

from . import parameters, permissions, schemas
from .models import User, db

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
    @api.paginate()
    def get(self, args):
        """
        List users
        """
        return User.query_search(args=args)

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
            if role == 'is_staff' or role == 'is_internal':
                abort(
                    HTTPStatus.FORBIDDEN,
                    f'Not permitted to set {role} role for a new user',
                )

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
                new_user = User.ensure_user(**args)
            AuditLog.user_create_object(
                log, new_user, msg=f'{new_user.email}', duration=timer.elapsed()
            )
        return new_user


@api.route('/search')
@api.login_required(oauth_scopes=['users:read'])
class UserElasticsearch(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': User,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.UserListSchema(many=True))
    @api.paginate()
    def get(self, args):
        search = {}
        args['total'] = True
        return User.elasticsearch(search, **args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': User,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.UserListSchema(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()
        args['total'] = True
        return User.elasticsearch(search, **args)


@api.route('/<uuid:user_guid>')
@api.resolve_object_by_model(User, 'user')
class UserByID(Resource):
    """
    Manipulations with a specific user.
    """

    # use base decorators here for permissions or schemas, as getting specific user data is "public"
    # with the schema being determined based on privileges below
    @api.response(schemas.PublicUserSchema(), dump=False)
    def get(self, user):
        """
        Get user details by ID.  This API will return a more detailed response if the current logged in user is authorized for the requested user.
        """
        from app.modules.users.permissions import rules

        if not current_user.is_anonymous and (
            rules.owner_or_privileged(current_user, user) or current_user.is_user_manager
        ):
            schema = schemas.DetailedUserSchema()
        else:
            schema = schemas.PublicUserSchema()
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
                is_internal=False,
                is_admin=True,
                is_staff=False,
                is_researcher=True,
                is_contributor=True,
                is_user_manager=True,
                is_data_manager=True,
                is_exporter=True,
                is_active=True,
                in_beta=True,
                in_alpha=True,
                update=True,
                send_verification=False,
            )
            admin.bypass_email_confirmation()
            log.info(
                'Success creating startup (houston) admin user via API: {!r}.'.format(
                    admin
                )
            )
            rtn = {
                'initialized': True,
                'edmInitialized': False,  # Default value, over-written next if True
            }

            # now we attempt to create on edm as well
            if is_extension_enabled('edm'):
                rtn['edmInitialized'] = current_app.edm.initialize_edm_admin_user(
                    email, password
                )

            if not rtn['edmInitialized']:
                log.warning('EDM admin user not created; previous may have existed.')
            return rtn


@api.route('/edm/sync')
@api.extension_required('edm')
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
@api.module_required('sightings')
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
        offset = args['offset']
        limit = args['limit']

        start = offset
        end = offset + limit
        return user.get_sightings_json(start, end)


@api.route('/<uuid:user_guid>/profile_image', doc=False)
@api.resolve_object_by_model(User, 'user')
class UserProfileByID(Resource):
    def get(self, user):
        if not user.profile_fileupload_guid:
            from io import StringIO

            empty_file = StringIO()
            return send_file(empty_file, attachment_filename='profile_image.jpg')
        else:
            profile_path = user.profile_fileupload.get_absolute_path()
            return send_file(profile_path, attachment_filename='profile_image.jpg')


@api.route('/reset_password_email')
class UserResetPasswordEmail(Resource):
    def post(self):
        try:
            email = json.loads(request.data)['email']
        except (json.decoder.JSONDecodeError, TypeError, KeyError):
            abort(
                400, 'JSON body needs to be in this format {"email": "user@example.org"}'
            )
        user = User.find(email=email)
        if not user:
            # Log for development purposes but do not show anything to the API user
            log.warning(f'User with email address {repr(email)} not found')
            return
        code = user.get_account_recovery_code()
        msg = Email(recipients=[user])
        reset_link = url_for('frontend.auth-code', code=code.accept_code, _external=True)
        msg.template('misc/password_reset', reset_link=reset_link)
        msg.send_message()


# h/t https://agustinus.kristia.de/techblog/2015/08/29/twitter-auth-flask/
@api.route('/social_callback/<string:service>')
@api.login_required(oauth_scopes=[])
class UserSocialCallback(Resource):
    def get(self, service):
        # this is true for now, but this might be more general later
        if not is_module_enabled('intelligent_agent'):
            abort(400, 'invalid')
        if not service or service != 'twitter':
            abort(400, 'invalid service')

        import tweepy

        from app.extensions.intelligent_agent.models import TwitterBot

        args = request.args
        ck = TwitterBot.get_site_setting_value('consumer_key')
        cs = TwitterBot.get_site_setting_value('consumer_secret')
        if not ck or not cs:
            raise ValueError('twitter consumer key/secret not set')
        try:
            # auth = tweepy.OAuth1UserHandler(ck, cs, callback=url_for('api.users_user_social_callback', service='twitter', _external=True))
            auth = tweepy.OAuth1UserHandler(ck, cs)
            auth.request_token = session['twitter_request_token']
            # oauth_token, oauth_verifier via url args
            access_token, access_token_secret = auth.get_access_token(
                args.get('oauth_verifier')
            )
            del session['twitter_request_token']
            auth.set_access_token(access_token, access_token_secret)
            api = tweepy.API(auth)
            user = api.verify_credentials(skip_status=True, include_entities=False)
            current_user.link_account(
                'twitter',
                {
                    'id': user.id_str,
                    'name': user.name,
                    'username': user.screen_name,
                    'location': user.location,
                    'description': user.description,
                    'profile_image_url': user.profile_image_url_https,
                },
            )
        except Exception as ex:
            log.error(f'twitter callback failed: {str(ex)}')
            abort(400, 'internal twitter error')
        return redirect('/settings')


@api.route('/social_auth_redirect/<string:service>')
@api.login_required(oauth_scopes=[])
class UserSocialAuthRedirect(Resource):
    def get(self, service):
        if not service or service != 'twitter':
            abort(400, 'invalid service')

        # right now twitter "social login" is connected to TwitterBot settings
        #  likely these two things should be decoupled a bit in settings
        import tweepy

        from app.extensions.intelligent_agent.models import TwitterBot

        ck = TwitterBot.get_site_setting_value('consumer_key')
        cs = TwitterBot.get_site_setting_value('consumer_secret')
        if not ck or not cs:
            abort(400, 'twitter consumer key/secret not set')
        auth = tweepy.OAuth1UserHandler(
            ck,
            cs,
            callback=url_for(
                'api.users_user_social_callback', service='twitter', _external=True
            ),
        )
        # need this for callback
        url = auth.get_authorization_url(signin_with_twitter=True)
        session['twitter_request_token'] = auth.request_token
        return redirect(url)


@api.route('/verify_account_email')
@api.login_required(oauth_scopes=[])
class UserVerifyAccountEmail(Resource):
    def post(self):
        current_user.send_verify_account_email()


if is_module_enabled('asset_groups'):
    from app.modules.asset_groups.schemas import BaseAssetGroupSightingSchema

    @api.route('/<uuid:user_guid>/asset_group_sightings')
    @api.module_required('sightings')
    @api.resolve_object_by_model(User, 'user')
    class UserAssetGroupSightings(Resource):
        """
        AssetGroupSightings for a given Houston user. Note that we use PaginationParameters,
        meaning by default this call returns 20 assetGroupSightings and will never return more
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
        @api.response(BaseAssetGroupSightingSchema(many=True))
        @api.paginate(PaginationParametersLatestFirst())
        def get(self, args, user):
            """
            Get AssetGroupSightings for user
            """
            return user.get_unprocessed_asset_group_sightings()
