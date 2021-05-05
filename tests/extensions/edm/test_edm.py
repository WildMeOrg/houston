# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import uuid

# this tests edm hostname & credentials configs


def test_edm_initializes(flask_app):
    flask_app.edm._ensure_initialized()
    # if we get this far, we may be a valid user but not one with sufficient privs on edm, so lets find out:
    response = flask_app.edm.get_dict('encounter.data', uuid.uuid4())
    # one should *only* get a 404 here (request allowed for user -- but not found) versus 401/403 or 5xx
    # a 401 or 403 means valid login for edm, but that login has bad permissions!
    # if you get a 200 here, see jon for a prize
    assert response.status_code == 404


def test_initialize_admin_user(flask_app):
    # this should fail as admin_user should exist and/or email address is invalid
    email = None
    password = 'test'
    success = flask_app.edm.initialize_edm_admin_user(email, password)
    assert not success


# test that we are running against minimal needed version
def test_edm_version(flask_app):
    return  # disabling until edm-version bug is fixed
    version_ok = flask_app.edm.version_check()
    assert version_ok
