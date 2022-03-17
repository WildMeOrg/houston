# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest
import datetime
from . import utils as user_utils

from tests.utils import module_unavailable
from app.modules import is_module_enabled


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
    flask_app_client, user_manager_user, auth_scopes, db, test_root, request
):
    # Add a profile image to user_manager_user
    from app.modules.fileuploads.models import FileUpload

    fup = FileUpload.create_fileupload_from_path(test_root / 'zebra.jpg', copy=True)
    user_manager_user.profile_fileupload = fup
    with db.session.begin():
        db.session.add(fup)
        db.session.merge(user_manager_user)
    request.addfinalizer(lambda: db.session.delete(fup))
    request.addfinalizer(lambda: db.session.merge(user_manager_user))
    request.addfinalizer(lambda: setattr(user_manager_user, 'profile_fileupload', None))

    # pylint: disable=invalid-name
    with flask_app_client.login(user_manager_user, auth_scopes=auth_scopes):
        response = flask_app_client.get('/api/v1/users/')

    assert response.status_code == 200
    assert response.content_type == 'application/json'
    assert isinstance(response.json, list)
    user = [u for u in response.json if u['email'] == user_manager_user.email]
    assert len(user) == 1

    desired_user_data = {
        'guid': str(user_manager_user.guid),
        'elasticsearchable': user_manager_user.elasticsearchable,
        'email': user_manager_user.email,
        'full_name': user_manager_user.full_name,
        'is_active': True,
        'is_contributor': True,
        'is_exporter': False,
        'is_internal': False,
        'is_staff': False,
        'is_researcher': False,
        'is_user_manager': True,
        'is_data_manager': False,
        'is_admin': False,
        'indexed': f'{user_manager_user.indexed.isoformat()}+00:00',
        'in_alpha': True,
        'in_beta': False,
        'is_email_confirmed': False,
        'profile_fileupload': {
            'created': f'{fup.created.isoformat()}+00:00',
            'elasticsearchable': fup.elasticsearchable,
            'updated': f'{fup.updated.isoformat()}+00:00',
            'guid': str(fup.guid),
            'indexed': f'{fup.indexed.isoformat()}+00:00',
            'mime_type': 'image/jpeg',
            'src': f'/api/v1/fileuploads/src/{fup.guid}',
        },
    }

    if is_module_enabled('missions'):
        desired_user_data['owned_missions'] = []
        desired_user_data['owned_mission_tasks'] = []

    assert user[0] == desired_user_data


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


def test_getting_user_info_by_authorized_user(
    flask_app_client, regular_user, user_manager_user
):
    # pylint: disable=invalid-name
    response = user_utils.read_user(
        flask_app_client, user_manager_user, regular_user.guid
    )

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
        response.close()


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_getting_sightings_for_user(
    flask_app_client, db, staff_user, researcher_1, request, test_root
):

    from tests.modules.sightings.resources import utils as sighting_utils

    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root
    )

    from app.modules.sightings.models import Sighting

    sighting_id = uuids['sighting']
    sighting = Sighting.query.get(sighting_id)

    assert sighting is not None
    assert sighting.encounters[0].owner is researcher_1
    assert str(researcher_1.get_sightings()[0].guid) == sighting_id

    response = user_utils.read_user_path(
        flask_app_client, researcher_1, f'{researcher_1.guid}/sightings'
    )

    assert response.status_code == 200
    assert response.content_type == 'application/json'
    assert isinstance(response.json, list)

    assert len(response.json) == 1
    sighting_json = response.json[0]

    assert sighting_json['guid'] == sighting_id
    assert sighting_json['stage'] == 'un_reviewed'
    assert sighting_json['unreviewed_start_time'] is not None


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_getting_asset_group_sightings_for_user(
    flask_app_client, db, staff_user, researcher_1, request, test_root
):

    from tests.modules.asset_groups.resources import utils as group_utils

    uuids = group_utils.create_simple_asset_group(
        flask_app_client, researcher_1, request, test_root
    )

    response = user_utils.read_user_path(
        flask_app_client, researcher_1, f'{researcher_1.guid}/asset_group_sightings'
    )

    assert response.status_code == 200
    assert response.content_type == 'application/json'
    assert isinstance(response.json, list)

    assert len(response.json) == 1
    ags = response.json[0]

    assert ags['asset_group_guid'] == uuids[0]
    assert ags['guid'] == uuids[1]
    assert ags['stage'] == 'curation'
