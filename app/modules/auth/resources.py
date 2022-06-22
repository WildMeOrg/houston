# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods,invalid-name,bad-continuation
"""
Auth resources
--------------
"""
import json
import logging
from urllib.parse import urlencode

from flask import current_app, redirect, request
from flask_login import current_user, login_user, logout_user

from app.extensions import oauth2
from app.extensions.api import Namespace, abort, api_v1
from app.modules.users.models import User
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus

from . import parameters, schemas
from .models import Code, CodeDecisions, CodeTypes, OAuth2Client, db
from .utils import create_session_oauth2_token, delete_session_oauth2_token

log = logging.getLogger(__name__)
api = Namespace('auth', description='Authentication')


def _generate_new_client(args):
    context = api.commit_or_abort(
        db.session, default_error_message='Failed to create a new OAuth2 client.'
    )
    with context:
        new_oauth2_client = OAuth2Client(user_guid=current_user.guid, **args)
        db.session.add(new_oauth2_client)
    return new_oauth2_client


@api.route('/sessions')
class OAuth2Sessions(Resource):
    """
    Login with Session.
    """

    @api.parameters(parameters.CreateOAuth2SessionParameters())
    @api.response(code=HTTPStatus.UNAUTHORIZED)
    @api.doc(id='create_oauth_session')
    def post(self, args):
        """
        Log-in via a new OAuth2 Session.
        """
        email = args['email']
        password = args['password']

        user = User.find(email=email, password=password)

        failure = None
        if user is not None:
            status = login_user(user, remember=False)

            if status:
                log.info('Logged in User via API: {!r}'.format(user))
                create_session_oauth2_token()
            else:
                failure = 'Account Disabled'
        else:
            failure = 'Account Not Found'

        if failure is None:
            response = {
                'success': True,
                'message': 'Session Created',
            }
            code = HTTPStatus.OK
        else:
            response = {
                'success': False,
                'message': failure,
            }
            code = HTTPStatus.UNAUTHORIZED

        return response, code

    @api.login_required(oauth_scopes=['auth:write'])
    def delete(self):
        """
        Log-out the active OAuth2 Session.
        """
        log.info('Logging out User via API: {!r}'.format(current_user))

        delete_session_oauth2_token()
        logout_user()

        response = {
            'success': True,
            'message': 'Session Deleted',
        }

        return response


@api.route('/clients')
@api.login_required(oauth_scopes=['auth:read'])
class OAuth2Clients(Resource):
    """
    Manipulations with OAuth2 clients.
    """

    @api.response(schemas.DetailedOAuth2ClientSchema(many=True))
    def get(self):
        """
        List of OAuth2 Clients.

        Returns a list of OAuth2 Clients starting from ``offset`` limited by
        ``limit`` parameter.
        """
        oauth2_clients = OAuth2Client.query
        oauth2_clients = oauth2_clients.filter(
            OAuth2Client.user_guid == current_user.guid,
            OAuth2Client.level != OAuth2Client.ClientLevels.confidential,
        )

        if oauth2_clients.count() == 0 and current_user.is_admin:
            default_scopes = list(
                api_v1.authorizations['oauth2_password']['scopes'].keys()
            )
            args_ = {
                'default_scopes': default_scopes,
            }
            _generate_new_client(args_)
            return self.get()

        return oauth2_clients

    @api.login_required(oauth_scopes=['auth:write'])
    @api.parameters(parameters.CreateOAuth2ClientParameters())
    @api.response(schemas.DetailedOAuth2ClientSchema())
    @api.response(code=HTTPStatus.FORBIDDEN)
    @api.response(code=HTTPStatus.CONFLICT)
    @api.doc(id='create_oauth_client')
    def post(self, args):
        """
        Create a new OAuth2 Client.

        Essentially, OAuth2 Client is a ``guid`` and ``secret``
        pair associated with a user.
        """
        new_oauth2_client = _generate_new_client(args)
        return new_oauth2_client


@api.route('/tokens')
# @api.login_required(oauth_scopes=['auth:read'], locations=('headers', 'session', 'form', ))
class OAuth2Tokens(Resource):
    """
    Manipulations with OAuth2 clients.
    """

    @oauth2.token_handler
    def post(self):
        """
        This endpoint is for exchanging/refreshing an access token.

        Returns:
            response (dict): a dictionary or None as the extra credentials for
            creating the token response.
        """
        return None


@api.route('/revoke')
@api.login_required(oauth_scopes=['auth:read'])
class OAuth2Revoke(Resource):
    """
    Manipulations with OAuth2 clients.
    """

    # @api.login_required(oauth_scopes=['auth:write'])
    @oauth2.revoke_handler
    def post(self):
        """
        This endpoint allows a user to revoke their access token.
        """
        return None


@api.route('/recaptcha')
class ReCaptchaPublicServerKey(Resource):
    """
    Use signup form helper for recaptcha.
    """

    @api.response(schemas.ReCaptchaPublicServerKeySchema())
    def get(self):
        """
        Get recaptcha form keys.

        This endpoint must be used in order to get a server reCAPTCHA public key which
        must be used to receive a reCAPTCHA secret key for POST /<prefix>/users/ form.
        """
        response = {
            'recaptcha_public_key': current_app.config.get('RECAPTCHA_PUBLIC_KEY', None),
        }
        return response


@api.route('/code/<string:code_string_dot_json>')
class CodeReceived(Resource):
    # Get and Post do the same thing so just encapsulate the functionality in one method
    def _action_code(self, code_string_dot_json):

        if code_string_dot_json.endswith('.json'):
            is_json = True
            code_string = code_string_dot_json[:-5]
        else:
            is_json = False
            code_string = code_string_dot_json

        decision, code = Code.received(code_string)
        if code is None:
            abort(404, f'Code {repr(code_string)} not found')

        redirect_uri = None
        url_args = {}
        if code.code_type == CodeTypes.recover:
            redirect_uri = '/reset_password'
        elif code.code_type == CodeTypes.email:
            # nothing to do because User.is_email_confirmed looks into Code for
            # the user filtered by CodeTypes.email is_resolved
            redirect_uri = '/email_verified'
        else:
            abort(404, f'Unrecognized code type: {code.code_type}')

        if decision == CodeDecisions.expired:
            url_args['message'] = 'Code has expired'
        elif decision == CodeDecisions.error:
            url_args['message'] = 'Code not found'
        elif decision == CodeDecisions.dismiss:
            url_args['message'] = 'Code already used'

        if url_args.get('message'):
            if is_json:
                abort(400, url_args['message'])
            url_args['status'] = 400
            return redirect(f'{redirect_uri}?{urlencode(url_args)}')

        try:
            data = json.loads(request.data)
        except json.decoder.JSONDecodeError:
            data = {}

        if code.code_type == CodeTypes.recover:
            try:
                code.user.set_password(data.get('password', ''))
                url_args['message'] = 'Password successfully set.'
                url_args['status'] = 200
            except Exception as e:
                code.response = None
                with db.session.begin():
                    db.session.merge(code)
                url_args['message'] = str(e)
                url_args['status'] = 400
        elif code.code_type == CodeTypes.email:
            # nothing to do because User.is_email_confirmed looks into Code for
            # the user filtered by CodeTypes.email is_resolved
            url_args['message'] = 'Email successfully verified.'
            url_args['status'] = 200
        else:
            abort(404, f'Unrecognized code type: {code.code_type}')

        if is_json:
            if url_args.get('status', 200) != 200:
                abort(url_args['status'], url_args.get('message'))
            return {'message': url_args.get('message')}
        return redirect(f'{redirect_uri}?{urlencode(url_args)}')

    def post(self, code_string_dot_json):
        """
        If using `/api/v1/auth/code/<string>.json`, the API returns
        something like
        `{"status": 200, "message": "Password successfully set."}`

        If using `/api/v1/auth/code/<string>`, the API redirects to
        something like
        `/email_verified?status=200&message=Email+successfully+verified`

        The difference between `.json` or not is whether the API
        redirects.

        More specific use cases:

        1. Email verification emails have a button that points to
        `/api/v1/auth/code/<string>` and so when the user clicks on it,
        back end deals with the code and redirects to
        `/email_verified?status=200&message=Email+successfully+verified`

        2. Reset password emails have a button that goes to a front end
        reset password form, and front end should POST
        `{"password": "<secret>"}` to
        `/api/v1/auth/code/<string>.json` so that it gets back the
        result in json format.
        """
        return self._action_code(code_string_dot_json)

    def get(self, code_string_dot_json):
        """
        If using `/api/v1/auth/code/<string>.json`, the API returns
        something like
        `{"status": 200, "message": "Password successfully set."}`

        If using `/api/v1/auth/code/<string>`, the API redirects to
        something like
        `/email_verified?status=200&message=Email+successfully+verified`

        The difference between `.json` or not is whether the API
        redirects.

        More specific use cases:

        1. Email verification emails have a button that points to
        `/api/v1/auth/code/<string>` and so when the user clicks on it,
        back end deals with the code and redirects to
        `/email_verified?status=200&message=Email+successfully+verified`

        2. Reset password emails have a button that goes to a front end
        reset password form, and front end should POST
        `{"password": "<secret>"}` to
        `/api/v1/auth/code/<string>.json` so that it gets back the
        result in json format.
        """
        return self._action_code(code_string_dot_json)
