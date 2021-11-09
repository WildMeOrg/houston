# -*- coding: utf-8 -*-
"""
Testing utils
-------------
"""

from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import tempfile

from flask import Response
from flask.testing import FlaskClient
from werkzeug.utils import cached_property
from app.extensions.auth import security
import redis
import random
import uuid
import os

from . import TEST_ASSET_GROUP_UUID, TEST_EMPTY_ASSET_GROUP_UUID

from flask_restx_patched import is_extension_enabled, is_module_enabled


class AutoAuthFlaskClient(FlaskClient):
    """
    A helper FlaskClient class with a useful for testing ``login`` context
    manager.
    """

    def __init__(self, *args, **kwargs):
        super(AutoAuthFlaskClient, self).__init__(*args, **kwargs)
        self._user = None
        self._auth_scopes = None

    @contextmanager
    def login(self, user, auth_scopes=None):
        """
        Here is an example of how to use the login context

        with flask_app_client.login(user, auth_scopes=['users:read']):
            flask_app_client.get('/api/v1/users/')
        """
        self._user = user
        self._auth_scopes = auth_scopes or []
        yield self
        self._user = None
        self._auth_scopes = None

    def open(self, *args, **kwargs):
        try:
            if self._user is not None:
                from app.extensions import db
                from app.modules.auth.models import OAuth2Client, OAuth2Token

                oauth2_client = OAuth2Client(
                    secret='SECRET',
                    user=self._user,
                    default_scopes=[],
                )

                oauth2_bearer_token = OAuth2Token(
                    client=oauth2_client,
                    user=self._user,
                    token_type='Bearer',
                    access_token='test_access_token',
                    scopes=self._auth_scopes,
                    expires=datetime.utcnow() + timedelta(days=1),
                )

                with db.session.begin():
                    db.session.add(oauth2_client)
                    db.session.add(oauth2_bearer_token)

                extra_headers = (
                    (
                        'Authorization',
                        '{token.token_type} {token.access_token}'.format(
                            token=oauth2_bearer_token
                        ),
                    ),
                )
                if kwargs.get('headers'):
                    kwargs['headers'] += extra_headers
                else:
                    kwargs['headers'] = extra_headers

            response = super(AutoAuthFlaskClient, self).open(*args, **kwargs)
        except Exception:
            raise
        finally:
            if self._user is not None:
                with db.session.begin():
                    db.session.delete(oauth2_bearer_token)
                    db.session.delete(oauth2_bearer_token.client)

        return response


class JSONResponse(Response):
    # pylint: disable=too-many-ancestors
    """
    A Response class with extra useful helpers, i.e. ``.json`` property.
    """

    @cached_property
    def json(self):
        return json.loads(self.get_data(as_text=True))


class TemporaryDirectoryGraceful(tempfile.TemporaryDirectory):
    def __exit__(self, *args, **kwargs):
        try:
            super(TemporaryDirectoryGraceful, self).__exit__(*args, **kwargs)
        except FileNotFoundError:
            assert not os.path.exists(self.name)


def generate_encounter_instance(user_email=None, user_password=None, user_full_name=None):
    """
    Returns:
        encounter_instance (Encounter) - a not committed to DB instance of a Encounter model.
    """
    user = generate_user_instance(
        email=user_email, password=user_password, full_name=user_full_name
    )
    from app.modules.encounters.models import Encounter

    return Encounter(owner=user, asset_group_sighting_encounter_guid=uuid.uuid4())


def generate_owned_encounter(owner):
    from app.modules.encounters.models import Encounter

    return Encounter(owner=owner, asset_group_sighting_encounter_guid=uuid.uuid4())


def generate_user_instance(
    user_guid=None,
    email=None,
    password=None,
    full_name='First Middle Last',
    created=None,
    updated=None,
    is_active=True,
    is_staff=False,
    is_admin=False,
    is_internal=False,
    is_researcher=False,
    is_contributor=True,
    is_user_manager=False,
    in_alpha=True,
):
    """
    Returns:
        user_instance (User) - an not committed to DB instance of a User model.
    """
    # pylint: disable=too-many-arguments
    from app.modules.users.models import User

    if user_guid is None:
        user_guid = uuid.uuid4()

    if email is None:
        email = '%s@localhost' % (email,)

    if password is None:
        password = security.generate_random(128)

    user_instance = User(
        guid=user_guid,
        full_name=full_name,
        password=password,
        email=email,
        created=created or datetime.now(),
        updated=updated or datetime.now(),
        is_active=is_active,
        is_staff=is_staff,
        is_admin=is_admin,
        is_internal=is_internal,
        is_researcher=is_researcher,
        is_contributor=is_contributor,
        is_user_manager=is_user_manager,
        in_alpha=in_alpha,
    )
    user_instance.password_secret = password
    return user_instance


def generate_asset_group_instance(owner):
    from app.modules.asset_groups.models import AssetGroup

    asset_group_instance = AssetGroup(guid=uuid.uuid4(), owner=owner)
    return asset_group_instance


def generate_asset_instance(asset_group_guid):
    from app.modules.assets.models import Asset

    asset_instance = Asset(
        guid=uuid.uuid4(),
        extension='None',
        path='FollowYourOwn',
        mime_type='Corporeal',
        magic_signature='42',
        filesystem_xxhash64='42',
        filesystem_guid=uuid.uuid4(),
        semantic_guid=uuid.uuid4(),
        asset_group_guid=asset_group_guid,
    )
    return asset_instance


def validate_dict_response(response, expected_code, expected_fields):
    assert response.status_code == expected_code, response.json
    # after some discussion, dropping the check of response.content_type
    # turns out response.json is very forgiving and tries to parse response.data
    # even when response.is_json == False ... so this allows for sloppy headers but valid json getting thru
    assert isinstance(response.json, dict)
    assert set(response.json.keys()) >= expected_fields, set(response.json.keys())


def validate_list_response(response, expected_code):
    assert response.status_code == expected_code
    assert response.content_type == 'application/json'
    assert isinstance(response.json, list)


def validate_list_of_dictionaries_response(response, expected_code, expected_fields):
    validate_list_response(response, expected_code)
    for item in response.json:
        assert isinstance(item, dict)
        assert set(item.keys()) >= expected_fields, set(item.keys())


def get_dict_via_flask(
    flask_app_client,
    user,
    scopes,
    path,
    expected_status_code,
    response_200,
    expected_error=None,
    response_error={'status', 'message'},
):
    if user:
        with flask_app_client.login(user, auth_scopes=(scopes,)):
            response = flask_app_client.get(path)
    else:
        response = flask_app_client.get(path)
    if expected_status_code == 200:
        validate_dict_response(response, 200, response_200)
    elif expected_status_code == 404:
        validate_dict_response(response, expected_status_code, {'message'})
    elif expected_status_code:
        # If expected status code is None, caller handles the validation
        validate_dict_response(response, expected_status_code, response_error)
        if expected_error:
            assert response.json['message'] == expected_error, response.json['message']
    return response


def get_list_via_flask(
    flask_app_client,
    user,
    scopes,
    path,
    expected_status_code,
    expected_error=None,
    expected_fields=None,
):
    if user:
        with flask_app_client.login(user, auth_scopes=(scopes,)):
            response = flask_app_client.get(path)
    else:
        response = flask_app_client.get(path)
    if expected_status_code == 200:
        if expected_fields:
            validate_list_of_dictionaries_response(
                response, expected_status_code, expected_fields
            )
            validate_list_response(response, 200)
    elif expected_status_code == 404:
        validate_dict_response(response, expected_status_code, {'message'})
    elif expected_status_code:
        # If expected status code is None, caller handles the validation
        validate_dict_response(response, expected_status_code, {'status', 'message'})
        if expected_error:
            assert response.json['message'] == expected_error, response.json['message']
    return response


def post_via_flask(
    flask_app_client,
    user,
    scopes,
    path,
    data,
    expected_status_code,
    response_200,
    expected_error=None,
):

    if user:
        with flask_app_client.login(user, auth_scopes=(scopes,)):
            response = flask_app_client.post(
                path,
                content_type='application/json',
                data=json.dumps(data),
            )
    else:
        response = flask_app_client.post(
            path,
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        validate_dict_response(response, 200, response_200)
    elif expected_status_code:
        validate_dict_response(response, expected_status_code, {'status', 'message'})
        if expected_error:
            assert response.json['message'] == expected_error, response.json['message']
    return response


def patch_via_flask(
    flask_app_client,
    user,
    scopes,
    path,
    data,
    expected_status_code,
    response_200,
    expected_error=None,
    headers=None,
):

    if user:
        with flask_app_client.login(user, auth_scopes=(scopes,)):
            response = flask_app_client.patch(
                path,
                content_type='application/json',
                data=json.dumps(data),
                headers=headers,
            )
    else:
        response = flask_app_client.patch(
            path, content_type='application/json', data=json.dumps(data), headers=headers
        )

    if expected_status_code == 200:
        validate_dict_response(response, 200, response_200)
    elif expected_status_code:
        # If no expected status code, leave the caller to handle it
        validate_dict_response(response, expected_status_code, {'status', 'message'})
        if expected_error:
            assert response.json['message'] == expected_error, response.json['message']
    return response


def delete_via_flask(
    flask_app_client,
    user,
    scopes,
    path,
    expected_status_code,
    expected_error=None,
):
    with flask_app_client.login(user, auth_scopes=(scopes,)):
        response = flask_app_client.delete(path)

    if expected_status_code == 204:
        assert response.status_code == 204
    else:
        validate_dict_response(response, expected_status_code, {'status', 'message'})
        if expected_error:
            assert response.json['message'] == expected_error, response.json['message']


def patch_test_op(value):
    return {
        'op': 'test',
        'path': '/current_password',
        'value': value,
    }


def patch_add_op(path, value):
    return {
        'op': 'add',
        'path': '/%s' % (path,),
        'value': value,
    }


def patch_remove_op(path, value=None):
    operation = {
        'op': 'remove',
        'path': '/%s' % (path,),
    }
    if value:
        operation['value'] = value

    return operation


def patch_replace_op(path, value):
    return {
        'op': 'replace',
        'path': '/%s' % (path,),
        'value': value,
    }


def all_count(db):
    from app.modules.sightings.models import Sighting
    from app.modules.encounters.models import Encounter
    from app.modules.assets.models import Asset
    from app.modules.asset_groups.models import AssetGroup
    from app.modules.individuals.models import Individual
    from app.modules.collaborations.models import Collaboration

    count = {}
    for cls in (Sighting, Encounter, Individual, Collaboration):
        count[cls.__name__] = row_count(db, cls)
    asset_query = Asset.query
    asset_group_query = AssetGroup.query
    for guid in (TEST_ASSET_GROUP_UUID, TEST_EMPTY_ASSET_GROUP_UUID):
        asset_query = asset_query.filter(Asset.asset_group_guid != guid)
        asset_group_query = asset_group_query.filter(AssetGroup.guid != guid)
    count['Asset'] = asset_query.count()
    count['AssetGroup'] = asset_group_query.count()
    return count


def row_count(db, cls):
    return db.session.query(cls).count()


def redis_unavailable(cached_value=[]):
    if len(cached_value) == 0:
        try:
            host = os.getenv('REDIS_HOST') or 'localhost'
            redis.Redis(host=host).get('test')
            cached_value.append(False)
        except redis.exceptions.ConnectionError:
            cached_value.append(True)
    return cached_value[0]


def extension_unavailable(*args, **kwargs):
    return not is_extension_enabled(*args, **kwargs)


def module_unavailable(*args, **kwargs):
    return not is_module_enabled(*args, **kwargs)


def random_decimal_latitude():
    return random.uniform(-90, 90)

def random_decimal_longitude():
    return random.uniform(-180, 80)
