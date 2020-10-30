# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Ecological Data Management (ACM) manager.

"""
import logging

from flask import current_app, request, session, render_template  # NOQA
from flask_login import current_user  # NOQA

# from app.extensions import db
import requests
from collections import namedtuple
import utool as ut

# import types
import json

import pytz

import keyword


KEYWORD_SET = set(keyword.kwlist)


log = logging.getLogger(__name__)

PST = pytz.timezone('US/Pacific')


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


class ACMManagerEndpointMixin(object):

    ENDPOINT_PREFIX = 'api'

    # We use // as a shorthand for prefix
    # fmt: off
    ENDPOINTS = {
        'session': {
            'login': '//v0/login?content={"login":"%s","password":"%s"}',
        },
    }
    # fmt: on

    def _endpoint_fmtstr(self, tag, target='default'):
        endpoint_tag_fmtstr = self._endpoint_tag_fmtstr(tag)
        assert endpoint_tag_fmtstr is not None, 'The endpoint tag was not recognized'

        if endpoint_tag_fmtstr.startswith('//'):
            endpoint_tag_fmtstr = endpoint_tag_fmtstr[2:]
            endpoint_tag_fmtstr = '%s/%s' % (
                self.ENDPOINT_PREFIX,
                endpoint_tag_fmtstr,
            )

        endpoint_url_ = self.get_target_endpoint_url(target)
        endpoint_fmtstr = '%s/%s' % (
            endpoint_url_,
            endpoint_tag_fmtstr,
        )
        return endpoint_fmtstr

    def _endpoint_tag_fmtstr(self, tag):
        endpoint = self.ENDPOINTS

        component_list = tag.split('.')
        for comoponent in component_list:
            try:
                endpoint_ = endpoint.get(comoponent, None)
            except Exception:
                endpoint_ = None

            if endpoint_ is None:
                break

            endpoint = endpoint_

        return endpoint


class ACMManager(ACMManagerEndpointMixin):
    # pylint: disable=abstract-method
    """
        note the content of User in the 2nd item has stuff you can ignore. it also has the id as "uuid" (which is what it is internally, sigh).  also note it references Organizations !  we didnt touch on this on the call, but i think this should (must?) live with Users.  what we have in java is very lightweight anyway, so no loss to go away.   as you can see, user.organizations is an array of orgs, and (since it is many-to-many) you will see org.members is a list of Users.  easy peasy.  btw, by the time we got to Organizations, we did call the primary key id and make it a uuid.  "live and learn".  :confused:
    also!  the user.profileAsset is fabricated!  ben wanted something so i literally hardcoded a random choice (including empty) from a list of like 4 user faces. haha.  so you arent going crazy if you see this change per user.  and obviously in the future the contents of this will be more whatever we land on for final asset format.

        btw, as a bonus.  here is what an Organization is on wildbook[acm] ... they are hierarchical -- which i would argue we drop!!  it was fun for playing with, but i do not want to have to support that when security starts using these!!!  (no real world orgs use this currently anyway, not in any important way.)   other than that (and killing it off!) there are .members and .logoAsset.  boringly simple.
    https://nextgen.dev-wildbook.org/api/org.ecocean.Organization?id==%273b868b21-729f-46ca-933f-c4ecdf02e97d%27
    """

    def __init__(self, app, pre_initialize=True, *args, **kwargs):
        super(ACMManager, self).__init__(*args, **kwargs)
        self.initialized = False

        self.app = app
        self.targets = set([])

        app.acm = self

        if pre_initialize:
            self.ensure_initialed()

    def _parse_config_acm_uris(self):
        import utool as ut

        ut.embed()

        acm_uri_dict = self.app.config.get('ACM_URIS', None)
        acm_authentication_dict = self.app.config.get('ACM_AUTHENTICATIONS', None)

        assert acm_uri_dict is not None, 'Must specify ACM_URIS in config'
        message = 'Must specify ACM_AUTHENTICATIONS in the secret config'
        assert acm_authentication_dict is not None, message

        try:
            key_list = []
            invalid_key_list = []

            acm_uri_key_list = sorted(acm_uri_dict.keys())
            acm_authentication_key_list = sorted(acm_authentication_dict.keys())

            for key in acm_uri_key_list:
                valid = True

                try:
                    if not isinstance(key, int):
                        # key isn't an integer or a parsable integer
                        try:
                            key_ = int(key)
                            key = key_
                        except Exception:
                            valid = False

                    if key < 0:
                        # key is negative
                        valid = False

                    if key in key_list + invalid_key_list:
                        # key seen before, no duplicates allowed
                        valid = False

                    if key >= len(acm_uri_key_list):
                        # key order is higher than the total, no skips allowed
                        valid = False

                    if key not in acm_authentication_key_list:
                        # Authentication not provided
                        valid = False

                except Exception:
                    valid = False

                if valid:
                    key_list.append(key)
                else:
                    invalid_key_list.append(key)

            if len(invalid_key_list) > 0:
                raise ValueError('Invalid keys provided')

        except Exception as exception:
            print('Invalid keys %r provided in ACM_URIS' % (invalid_key_list,))
            raise exception

        key_list = sorted(key_list)

        assert 0 in key_list, 'ACM_URIS must contain an integer key 0'
        assert len(key_list) == len(set(key_list)), 'ACM_URIS cannot contain duplicates'
        assert key_list[0] == 0, 'ACM_URIS is mis-configured'
        assert key_list[-1] == len(key_list) - 1, 'ACM_URIS is mis-configured'

        uris = {}
        auths = {}
        for key in key_list:
            if key == 0:
                uris['default'] = acm_uri_dict[key]
                auths['default'] = acm_authentication_dict[key]
                self.targets.add('default')
            uris[key] = acm_uri_dict[key]
            auths[key] = acm_authentication_dict[key]
            self.targets.add(key)

        self.uris = uris
        self.auths = auths

    def _init_sessions(self):
        self.sessions = {}
        for target in self.uris:
            auth = self.auths[target]

            email = auth.get('username', auth.get('email', None))
            password = auth.get('password', auth.get('pass', None))

            message = 'ACM Authentication for %s unspecified (email)' % (target,)
            assert email is not None, message
            message = 'ACM Authentication for %s unspecified (password)' % (target,)
            assert password is not None, message

            self.sessions[target] = requests.Session()
            self._get(
                'session.login', email, password, target=target, ensure_initialized=False
            )
            log.info('Created authenticated session for ACM target %r' % (target,))

    def ensure_initialed(self):
        if not self.initialized:
            log.info('Initializing ACM')
            self._parse_config_acm_uris()
            self._init_sessions()
            log.info('\t%s' % (ut.repr3(self.uris)))
            log.info('ACM Manager is ready')
            self.initialized = True

    def get_target_endpoint_url(self, target='default'):
        endpoint_url = self.uris[target]
        endpoint_url_ = endpoint_url.strip('/')
        return endpoint_url_

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
        verbose=True
    ):
        if ensure_initialized:
            self.ensure_initialed()

        method = method.lower()
        assert method in ['get', 'post', 'delete', 'put']

        if endpoint is None:
            assert tag is not None
            endpoint_fmtstr = self._endpoint_fmtstr(tag, target=target)
            endpoint = endpoint_fmtstr % args

        if tag is None:
            assert endpoint is not None

        endpoint_encoded = requests.utils.quote(endpoint, safe='/?:=')

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

        return response

    def _get(self, *args, **kwargs):
        return self._request('get', *args, **kwargs)

    def _post(self, *args, **kwargs):
        return self._request('post', *args, **kwargs)

    def get_passthrough(self, *args, **kwargs):
        response = self._get(*args, **kwargs)
        return response

    def post_passthrough(self, *args, **kwargs):
        response = self._post(*args, **kwargs)
        return response


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    API extension initialization point.
    """
    ACMManager(app)
