# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Rest Manager base class, to be used for any entity (EDM/ACM) where we need to interface with an external
system using REST API

"""
import logging
from werkzeug.exceptions import BadRequest
from flask import current_app, request, session, render_template  # NOQA
from flask_login import current_user  # NOQA
import requests
from collections import namedtuple
import utool as ut
import json
import keyword
import uuid

KEYWORD_SET = set(keyword.kwlist)

log = logging.getLogger(__name__)


def _json_object_hook(data):
    keys = list(data.keys())
    keys_set = set(keys)
    keys_ = []
    for key in keys:
        if key in KEYWORD_SET:
            key_ = '%s_' % (key,)
            assert key_ not in keys_set
        else:
            key_ = key
        keys_.append(key_)
    values = data.values()
    data_ = namedtuple('obj', keys_)(*values)
    return data_


# Not entirely certain how appropriate this is as a Mixin as it's dependent on a couple of things in
# the main class
class RestManagerUserMixin(object):
    def check_user_login(self, username, password):
        self._ensure_initialized()

        success = False
        for target in self.targets:
            # Create temporary session
            temporary_session = requests.Session()
            try:
                response = self._get(
                    'session.login',
                    username,
                    password,
                    target=target,
                    target_session=temporary_session,
                )

                assert response.ok
                decoded_response = response.json()
                assert decoded_response['message']['key'] == 'success'

                log.info(f'User authenticated via {self.NAME} (target = {target})')
                success = True
                break
            except Exception:
                pass
            finally:
                # Cleanup temporary session
                temporary_session.cookies.clear_session_cookies()
                temporary_session.close()

        return success


class RestManager(RestManagerUserMixin):
    # pylint: disable=abstract-method

    ENDPOINT_PREFIX = None
    ENDPOINTS = None
    NAME = None

    def __init__(self, require_login=True, pre_initialize=False, *args, **kwargs):
        super(RestManager, self).__init__(*args, **kwargs)
        self.initialized = False

        # Must be overwritten by the derived class
        assert self.NAME is not None
        assert self.ENDPOINT_PREFIX is not None
        assert self.ENDPOINTS is not None

        self.require_login = require_login

        self.targets = set([])

        if pre_initialize:
            self._ensure_initialized()

    def _endpoint_fmtstr(self, tag, target='default'):
        endpoint_tag_fmtstr = self._endpoint_tag_fmtstr(tag)
        assert endpoint_tag_fmtstr is not None, 'The endpoint tag was not recognized'

        if endpoint_tag_fmtstr.startswith('//'):
            endpoint_tag_fmtstr = endpoint_tag_fmtstr[2:]
            endpoint_tag_fmtstr = f'{self.ENDPOINT_PREFIX}/{endpoint_tag_fmtstr}'

        endpoint_url_ = self.get_target_endpoint_url(target)
        endpoint_fmtstr = f'{endpoint_url_}/{endpoint_tag_fmtstr}'
        return endpoint_fmtstr

    def _endpoint_tag_fmtstr(self, tag):
        endpoint = self.ENDPOINTS

        component_list = tag.split('.')
        for component in component_list:
            try:
                endpoint_ = endpoint.get(component, None)
            except Exception:
                endpoint_ = None

            if endpoint_ is None:
                break

            endpoint = endpoint_

        return endpoint

    def _parse_config_uris(self):
        uris = current_app.config.get(f'{self.NAME}_URIS', {})
        # Check for the 'default'
        assert uris.get('default'), f"Missing a 'default' {self.NAME}_URI"

        # Update the list of known named targets
        self.targets.update(uris.keys())

        # Assign local references to the configuration settings
        self.uris = uris

    def _parse_config_auths(self):
        """Obtain and verify the required configuration settings and
        update the list of known EDM targets by URI.

        This procedure is primarily focused on matching a URI to
        authentication credentials. It ignores matching in the other direction.

        """
        authns = current_app.config.get(f'{self.NAME}_AUTHENTICATIONS', {})

        has_required_default_authn = (
            isinstance(authns.get('default'), dict)
            and authns['default'].get('username')
            and authns['default'].get('password')
        )
        assertion_msg = f"Missing {self.NAME}_AUTHENTICATIONS credentials for 'default'"
        assert has_required_default_authn, assertion_msg

        # Check URIs have matching credentials
        missing_creds = [k for k in self.uris.keys() if not authns.get(k)]
        assert (
            not missing_creds
        ), f"Missing credentials for named {self.NAME} configs: {', '.join(missing_creds)}"

        # Assign local references to the configuration settings
        self.auths = authns

    def _init_sessions(self):
        self.sessions = {}
        for target in self.uris:
            self.sessions[target] = requests.Session()

            if self.require_login:
                auth = self.auths[target]

                email = auth.get('username', auth.get('email', None))
                password = auth.get('password', auth.get('pass', None))

                message = f'{self.NAME} Authentication for {target} unspecified (email)'
                assert email is not None, message
                message = (
                    f'{self.NAME} Authentication for {target} unspecified (password)'
                )
                assert password is not None, message

                response = self._get(
                    'session.login',
                    email,
                    password,
                    target=target,
                    ensure_initialized=False,
                )
                assert (
                    not isinstance(response, requests.models.Response) or response.ok
                ), f'{self.NAME} Authentication for {target} returned non-OK code: {response.status_code}'

            log.info(f'Created authenticated session for {self.NAME} target {target}')

    def pseudo_initialize(self, target):
        """
        Basically gives us the ability to create a session for a target which _does not_ rely
        on actually having authentication credentials.  This is useful for requests to the EDM which
        do not need authentication, like configuration reading and first-time admin creation.

        """
        if not self.initialized:
            log.debug('Pseudo-initializing')
            self.sessions = {}
            self.sessions[target] = requests.Session()
            self._parse_config_uris()

    def _ensure_initialized(self):
        if not self.initialized:
            log.info('Initializing %s' % self.NAME)
            self._parse_config_uris()
            if self.require_login:
                self._parse_config_auths()
            self._init_sessions()
            log.info('\t%s' % (ut.repr3(self.uris)))
            log.info('%s Manager is ready' % self.NAME)
            self.initialized = True

    def get_target_endpoint_url(self, target='default'):
        endpoint_url = self.uris[target]
        endpoint_url_ = endpoint_url.strip('/')
        return endpoint_url_

    def get_target_list(self):
        self._ensure_initialized()
        return list(self.targets)

    def _request(
        self,
        method,
        tag,
        *args,
        endpoint=None,
        target='default',
        target_session=None,
        _pre_request_func=None,
        decode_as_object=True,
        decode_as_dict=False,
        passthrough_kwargs={},
        ensure_initialized=True,
        verbose=True,
    ):
        if ensure_initialized:
            self._ensure_initialized()
        method = method.lower()
        assert method in ['get', 'post', 'delete', 'put', 'patch']

        if endpoint is None:
            assert tag is not None
            endpoint_fmtstr = self._endpoint_fmtstr(tag, target=target)
            if len(args) == 1 and args[0] is None:
                endpoint = endpoint_fmtstr
            else:
                endpoint = endpoint_fmtstr % args

        if tag is None:
            assert endpoint is not None

        endpoint_encoded = requests.utils.quote(endpoint, safe='/?:=&')

        if verbose:
            log.info('Sending request to: %r' % (endpoint_encoded,))

        if target_session is None:
            target_session = self.sessions[target]

        with target_session:
            if _pre_request_func is not None:
                target_session = _pre_request_func(target_session)

            request_func = getattr(target_session, method, None)
            assert request_func is not None

            response = request_func(endpoint_encoded, **passthrough_kwargs)

        if response.ok:
            if decode_as_object and decode_as_dict:
                log.warning(
                    'Both decode_object and decode_dict are True, defaulting to object'
                )
                decode_as_dict = False

            if decode_as_object:
                response = json.loads(response.text, object_hook=_json_object_hook)

            if decode_as_dict:
                response = response.json()
        else:
            log.warning(
                f'Non-OK ({response.status_code}) response on {method} {endpoint}: {response.content}'
            )

        return response

    def _get(self, *args, **kwargs):
        return self._request('get', *args, **kwargs)

    def _post(self, *args, **kwargs):
        return self._request('post', *args, **kwargs)

    def _delete(self, *args, **kwargs):
        return self._request('delete', *args, **kwargs)

    def get_list(self, list_name, target='default'):
        response = self._get(list_name, target=target)

        items = {}
        for value in response:
            try:
                guid = value.id
                version = value.version
            except AttributeError as exception:
                log.error(f'Invalid response from {self.NAME} [{list_name}]')
                raise exception

            guid = uuid.UUID(guid)
            assert isinstance(version, int)

            items[guid] = {'version': version}

        return items

    def get_dict(self, list_name, guid, target='default'):

        assert isinstance(guid, uuid.UUID)
        response = self._get(
            list_name,
            guid,
            target=target,
            decode_as_object=False,
            decode_as_dict=True,
        )
        return response

    def get_data_item(self, guid, item_name, target='default'):
        assert isinstance(guid, uuid.UUID)
        response = self._get(item_name, guid, target=target)
        return response

    def request_passthrough(
        self, tag, method, passthrough_kwargs, args=None, target='default'
    ):
        self._ensure_initialized()
        try:
            # Try to convert string integers to integers
            target = int(target)
        except ValueError:
            pass

        # Check target
        targets = list(self.targets)
        if target not in targets:
            raise BadRequest('The specified target %r is invalid.' % (target,))

        headers = passthrough_kwargs.get('headers', {})
        allowed_header_key_list = [
            'Accept',
            'Content-Type',
            'User-Agent',
        ]
        is_json = False
        for header_key in allowed_header_key_list:
            header_value = request.headers.get(header_key, None)
            header_existing = headers.get(header_key, None)
            if header_value is not None and header_existing is None:
                headers[header_key] = header_value

            if header_key == 'Content-Type':
                if header_value is not None:
                    if header_value.lower().startswith(
                        'application/javascript'
                    ) or header_value.lower().startswith('application/json'):
                        is_json = True
        passthrough_kwargs['headers'] = headers

        if is_json:
            data_ = passthrough_kwargs.pop('data', None)
            if data_ is not None:
                passthrough_kwargs['json'] = data_

        response = self._request(
            method,
            tag,
            args,
            target=target,
            decode_as_object=False,
            decode_as_dict=False,
            passthrough_kwargs=passthrough_kwargs,
        )
        return response
