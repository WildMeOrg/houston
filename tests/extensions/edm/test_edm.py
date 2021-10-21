# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import uuid
import pytest
from unittest import mock

from tests.utils import extension_unavailable

# this tests edm hostname & credentials configs


@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
def test_edm_initializes(flask_app):
    flask_app.edm._ensure_initialized()
    # if we get this far, we may be a valid user but not one with sufficient privs on edm, so lets find out:
    response = flask_app.edm.get_dict('encounter.data', uuid.uuid4())
    # one should *only* get a 404 here (request allowed for user -- but not found) versus 401/403 or 5xx
    # a 401 or 403 means valid login for edm, but that login has bad permissions!
    # if you get a 200 here, see jon for a prize
    assert response.status_code == 404


@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
def test_initialize_admin_user(flask_app):
    # this should fail as admin_user should exist and/or email address is invalid
    email = None
    password = 'test'
    success = flask_app.edm.initialize_edm_admin_user(email, password)
    assert not success


# test that we are running against minimal needed version
@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
def test_edm_version(flask_app):
    version_ok = flask_app.edm.version_check()
    assert version_ok


@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
def test_reauthentication(flask_app):
    flask_app.edm._ensure_initialized()
    original_get = flask_app.edm.sessions['default'].get
    mock_401 = mock.Mock(status_code=401, ok=False, content=b'')
    edm_uri = flask_app.config['EDM_URIS']['default']

    def mock_get(url, *args, call_count=[], **kwargs):
        if call_count == []:
            call_count.append(1)
            return mock_401
        return original_get(url, *args, **kwargs)

    with mock.patch.object(
        flask_app.edm.sessions['default'], 'get', side_effect=mock_get
    ) as edm_get:
        random_id = uuid.uuid4()
        result = flask_app.edm.get_dict('encounter.data', random_id)
        assert result.status_code == 404
        urls = [i[0][0] for i in edm_get.call_args_list]
        assert len(urls) == 3
        assert urls[0] == urls[2] == f'{edm_uri}api/v0/org.ecocean.Encounter/{random_id}'
        assert urls[1].startswith(f'{edm_uri}api/v0/login?')
