# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest
from tests import utils
import datetime

timestamp = datetime.datetime.now().isoformat() + 'Z'


@pytest.mark.parametrize(
    'auth_scopes',
    (
        ('users:write',),
        ('users:read',),
        (
            'users:read',
            'users:write',
        ),
    ),
)
def test_getting_list_of_users_by_unauthorized_user_must_fail(
    flask_app_client, regular_user, auth_scopes
):
    # pylint: disable=invalid-name
    with flask_app_client.login(regular_user, auth_scopes=auth_scopes):
        response = flask_app_client.get('/api/v1/users/')

    if 'users:read' in auth_scopes:
        assert response.status_code == 403
    else:
        assert response.status_code == 401
    assert response.content_type == 'application/json'
    assert set(response.json.keys()) >= {'status', 'message'}


@pytest.mark.parametrize(
    'auth_scopes',
    (
        ('users:read',),
        (
            'users:read',
            'users:write',
        ),
    ),
)
def test_getting_list_of_users_by_authorized_user(
    flask_app_client, user_manager_user, auth_scopes
):
    # pylint: disable=invalid-name
    with flask_app_client.login(user_manager_user, auth_scopes=auth_scopes):
        response = flask_app_client.get('/api/v1/users/')

    assert response.status_code == 200
    assert response.content_type == 'application/json'
    assert isinstance(response.json, list)
    assert set(response.json[0].keys()) >= {'guid', 'email'}


def test_getting_user_info_by_unauthorized_user(
    flask_app_client, regular_user, admin_user
):
    # pylint: disable=invalid-name
    with flask_app_client.login(regular_user, auth_scopes=('users:read',)):
        response = flask_app_client.get('/api/v1/users/%s' % admin_user.guid)

    assert response.status_code == 200
    assert response.content_type == 'application/json'
    assert isinstance(response.json, dict)
    assert set(response.json.keys()) == {'full_name', 'guid', 'profile_fileupload'}


def test_getting_user_info_by_authorized_user(flask_app_client, regular_user, admin_user):
    # pylint: disable=invalid-name
    with flask_app_client.login(admin_user, auth_scopes=('users:read',)):
        response = flask_app_client.get('/api/v1/users/%s' % regular_user.guid)

    assert response.status_code == 200
    assert response.content_type == 'application/json'
    assert isinstance(response.json, dict)
    assert set(response.json.keys()) >= {'guid', 'email'}
    assert 'password' not in response.json.keys()


def test_getting_user_info_by_owner(flask_app_client, regular_user):
    # pylint: disable=invalid-name
    with flask_app_client.login(regular_user, auth_scopes=('users:read',)):
        response = flask_app_client.get('/api/v1/users/%s' % regular_user.guid)

    assert response.status_code == 200
    assert response.content_type == 'application/json'
    assert isinstance(response.json, dict)
    assert set(response.json.keys()) >= {'guid', 'email'}
    assert 'password' not in response.json.keys()


def test_getting_user_me_info(flask_app_client, regular_user):
    # pylint: disable=invalid-name
    with flask_app_client.login(regular_user, auth_scopes=('users:read',)):
        response = flask_app_client.get('/api/v1/users/me')

    assert response.status_code == 200
    assert response.content_type == 'application/json'
    assert isinstance(response.json, dict)
    assert set(response.json.keys()) >= {'guid', 'email'}
    assert 'password' not in response.json.keys()


def test_getting_user_id_not_found(flask_app_client, regular_user):
    with flask_app_client.login(
        regular_user,
        auth_scopes=(
            'users:read',
            'users:write',
        ),
    ):
        response = flask_app_client.get('/api/v1/users/wrong-uuid')
        assert response.status_code == 404


def test_getting_sightings_for_user(flask_app_client, db, staff_user):

    from tests.modules.sightings.resources import utils as sighting_utils

    temp_owner = utils.generate_user_instance(
        email='user_4_sightings@localhost',
        is_researcher=True,
    )

    data_in = {
        'encounters': [{}],
        'startTime': '2000-01-01T01:01:01Z',
        'locationId': 'test',
    }

    sighting_create_response = sighting_utils.create_sighting(
        flask_app_client, temp_owner, data_in
    )

    from app.modules.sightings.models import Sighting

    sighting_id = sighting_create_response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)

    assert sighting_create_response.json['success']
    assert sighting is not None
    assert sighting.encounters[0].owner is temp_owner
    assert str(temp_owner.get_sightings()[0].guid) == sighting_id

    with flask_app_client.login(temp_owner, auth_scopes=('users:read',)):
        response = flask_app_client.get('/api/v1/users/%s/sightings' % (temp_owner.guid))

    assert response.status_code == 200
    assert response.content_type == 'application/json'
    assert isinstance(response.json, dict)

    assert response.json['sightings'] is not None
    assert response.json['sightings'][0]['id'] == sighting_id
    assert response.json['success'] is True

    # cleanup time
    sighting_utils.delete_sighting(flask_app_client, temp_owner, sighting_id)
    with db.session.begin():
        db.session.delete(temp_owner)
