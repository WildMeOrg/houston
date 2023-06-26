# -*- coding: utf-8 -*-
"""
Testing utils
-------------
"""

import datetime
import json
import logging
import os
import random
import tempfile
import time
import uuid
from contextlib import contextmanager

import redis
from flask import Response
from flask.testing import FlaskClient
from werkzeug.utils import cached_property

from app.extensions.auth import security
from config import get_preliminary_config
from flask_restx_patched import is_extension_enabled, is_module_enabled

from . import TEST_ASSET_GROUP_UUID, TEST_EMPTY_ASSET_GROUP_UUID


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
        from app.extensions import db
        from app.modules.auth.models import OAuth2Client, OAuth2Token

        oauth2_client_guid = None
        oauth2_bearer_token_guid = None
        try:
            if self._user is not None:
                oauth2_client = OAuth2Client(
                    secret='SECRET',
                    user=self._user,
                    default_scopes=[],
                )
                oauth2_client_guid = oauth2_client.guid

                oauth2_bearer_token = OAuth2Token(
                    client=oauth2_client,
                    user=self._user,
                    token_type='Bearer',
                    access_token='test_access_token',
                    scopes=self._auth_scopes,
                    expires=datetime.datetime.utcnow() + datetime.timedelta(days=1),
                )
                oauth2_bearer_token_guid = oauth2_bearer_token.guid

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
            with db.session.begin():
                if oauth2_bearer_token_guid is not None:
                    oauth2_bearer_token_ = OAuth2Token.query.get(oauth2_bearer_token_guid)
                    if oauth2_bearer_token_:
                        db.session.delete(oauth2_bearer_token_)

                if oauth2_client_guid is not None:
                    oauth2_client_ = OAuth2Client.query.get(oauth2_client_guid)
                    if oauth2_client_:
                        db.session.delete(oauth2_client_)

        return response


class JSONResponse(Response):
    # pylint: disable=too-many-ancestors
    """
    A Response class with extra useful helpers, i.e. ``.json`` property.
    """

    @cached_property
    def json(self):
        return json.loads(self.get_data(as_text=True))


class RandomUUIDSequence:
    """An instance of _RandomUUIDSequence generates an endless
    sequence of unpredictable strings which can safely be incorporated
    into file names.  Each string is eight characters long.  Multiple
    threads can safely use the same instance at the same time.

    _RandomUUIDSequence is an iterator."""

    def __iter__(self):
        return self

    def __next__(self):
        import uuid

        return str(uuid.uuid4())


class TemporaryDirectoryUUID(tempfile.TemporaryDirectory):
    def __init__(self, *args, **kwargs):
        tempfile._name_sequence = RandomUUIDSequence()

        super(TemporaryDirectoryUUID, self).__init__(*args, **kwargs)

    def __exit__(self, *args, **kwargs):
        try:
            super(TemporaryDirectoryUUID, self).__exit__(*args, **kwargs)
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
        email = '{}@localhost'.format(email)

    if password is None:
        password = security.generate_random(128)

    user_instance = User(
        guid=user_guid,
        full_name=full_name,
        password=password,
        email=email,
        created=created or datetime.datetime.now(),
        updated=updated or datetime.datetime.now(),
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


def generate_asset_instance(git_store_guid):
    from app.modules.assets.models import Asset

    asset_instance = Asset(
        guid=uuid.uuid4(),
        path='FollowYourOwn',
        mime_type='Corporeal',
        magic_signature='42',
        filesystem_xxhash64='42',
        filesystem_guid=uuid.uuid4(),
        semantic_guid=uuid.uuid4(),
        git_store_guid=git_store_guid,
    )
    return asset_instance


def validate_dict_response(response, expected_code, expected_fields):
    assert response.status_code == expected_code, response.json
    # after some discussion, dropping the check of response.content_type
    # turns out response.json is very forgiving and tries to parse response.data
    # even when response.is_json == False ... so this allows for sloppy headers but valid json getting thru
    assert isinstance(response.json, dict), response.json
    assert set(response.json.keys()) >= expected_fields, set(response.json.keys())


def validate_list_response(response, expected_code):
    assert response.status_code == expected_code
    assert response.content_type == 'application/json'
    assert isinstance(response.json, list), response.json


def validate_list_of_dictionaries_response(response, expected_code, expected_fields):
    validate_list_response(response, expected_code)
    for item in response.json:
        assert isinstance(item, dict), item
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
        if response_200 is not None:
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
    returns_list=False,
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

    if returns_list:
        if response.status_code == 200:
            validate_list_response(response, expected_status_code)
        else:  # this assumes non-200 does *not* return a list
            assert response.status_code == expected_status_code
    elif expected_status_code == 200:
        if response_200:
            validate_dict_response(response, 200, response_200)
        else:
            assert response.status_code == expected_status_code, response.json
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
        assert response.status_code == 204, response.status_code
    else:
        validate_dict_response(response, expected_status_code, {'status', 'message'})
        if expected_error:
            assert response.json['message'] == expected_error, response.json['message']


def patch_test_op(value, path='current_password', guid=None):
    operation = {
        'op': 'test',
        'path': '/{}'.format(path),
        'value': value,
    }
    if guid is not None:
        operation['guid'] = str(guid)
    return operation


def patch_add_op(path, value, guid=None):
    operation = {
        'op': 'add',
        'path': '/{}'.format(path),
        'value': value,
    }
    if guid is not None:
        operation['guid'] = str(guid)
    return operation


def patch_remove_op(path, value=None, guid=None):
    operation = {
        'op': 'remove',
        'path': '/{}'.format(path),
    }
    if value:
        operation['value'] = value
    if guid is not None:
        operation['guid'] = str(guid)
    return operation


def patch_replace_op(path, value, guid=None):
    operation = {
        'op': 'replace',
        'path': '/{}'.format(path),
        'value': value,
    }
    if guid is not None:
        operation['guid'] = str(guid)
    return operation


def set_union_op(path, value):
    operation = {
        'op': 'union',
        'path': '/{}'.format(path),
        'value': value,
    }
    return operation


def set_intersection_op(path, value):
    operation = {
        'op': 'intersection',
        'path': '/{}'.format(path),
        'value': value,
    }
    return operation


def set_difference_op(path, value):
    operation = {
        'op': 'difference',
        'path': '/{}'.format(path),
        'value': value,
    }
    return operation


def set_or_op(*args, **kwargs):
    return set_union_op(*args, **kwargs)


def set_and_op(*args, **kwargs):
    return set_intersection_op(*args, **kwargs)


def all_count(db):
    classes = []
    if is_module_enabled('sightings'):
        from app.modules.sightings.models import Sighting

        classes.append(Sighting)
    if is_module_enabled('encounters'):
        from app.modules.encounters.models import Encounter

        classes.append(Encounter)
    if is_module_enabled('individuals'):
        from app.modules.individuals.models import Individual

        classes.append(Individual)
    if is_module_enabled('collaborations'):
        from app.modules.collaborations.models import Collaboration

        classes.append(Collaboration)

    count = {}
    for cls in classes:
        count[cls.__name__] = row_count(db, cls)

    if is_module_enabled('assets', 'asset_groups'):
        from app.modules.asset_groups.models import AssetGroup
        from app.modules.assets.models import Asset

        asset_query = Asset.query
        asset_group_query = AssetGroup.query
        for guid in (TEST_ASSET_GROUP_UUID, TEST_EMPTY_ASSET_GROUP_UUID):
            asset_query = asset_query.filter(Asset.git_store_guid != guid)
            asset_group_query = asset_group_query.filter(AssetGroup.guid != guid)
        count['Asset'] = asset_query.count()
        count['AssetGroup'] = asset_group_query.count()
    else:
        count['Asset'] = 0
        count['AssetGroup'] = 0
    return count


def row_count(db, cls):
    return db.session.query(cls).count()


def redis_unavailable(cached_value=[]):
    if len(cached_value) == 0:
        config = get_preliminary_config(environment='testing')
        try:
            url = config.REDIS_CONNECTION_STRING
            redis.from_url(url).get('test')
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


def random_uuid():
    import uuid

    return uuid.uuid4()


def random_guid():
    return random_uuid()


def random_nonce(length=16):
    import string

    return ''.join(random.choice(string.ascii_letters) for character in range(length))


def isoformat_timestamp_now():
    return datetime.datetime.now().isoformat() + '+00:00'


def complex_date_time_now():
    from app.modules.complex_date_time.models import ComplexDateTime, Specificities

    return ComplexDateTime(datetime.datetime.utcnow(), 'UTC+00:00', Specificities.time)


def dummy_form_group_data(transaction_id):
    return {
        'uploadType': 'form',
        'description': 'This is a test asset group',
        'transactionId': transaction_id,
        'speciesDetectionModel': ['None'],
        'sightings': [dummy_sighting_info()],
    }


# What the FE sends so a good start point for tests
def dummy_sighting_info(time_specificity='time'):
    return {
        'time': isoformat_timestamp_now(),
        'timeSpecificity': time_specificity,
        'decimalLatitude': None,
        'decimalLongitude': None,
        'comments': '',
        'locationId': get_valid_location_id(),
        'encounters': [dummy_encounter_data(time_specificity)],
        'assetReferences': [],
    }


# What the FE sends so a good start point for tests
def dummy_encounter_data(time_specificity='time'):
    return {
        'decimalLatitude': None,
        'decimalLongitude': None,
        'locationId': get_valid_location_id(),
        'sex': None,
        'taxonomy': None,
        'verbatimLocality': '',
        'time': isoformat_timestamp_now(),
        'timeSpecificity': time_specificity,
    }


def dummy_detection_info():
    return ['None']


def get_stored_path(full_path):
    import os

    from app.utils import get_stored_filename

    dir, filename = os.path.split(full_path)
    stored_filename = get_stored_filename(filename)
    return os.path.join(dir, stored_filename)


def create_transaction_dir(flask_app, transaction_id):
    import pathlib

    tus_dir = pathlib.Path(flask_app.config['UPLOADS_DATABASE_PATH'])
    trans_dir = tus_dir / f'trans-{transaction_id}'
    trans_dir.mkdir(parents=True, exist_ok=True)
    return trans_dir


def write_uploaded_file(initial_filename, input_dir, file_data, write_mode='w'):
    from app.extensions.tus import tus_write_file_metadata

    if not isinstance(input_dir, str):
        input_dir = str(input_dir)
    if not isinstance(initial_filename, str):
        initial_filename = str(initial_filename)
    stored_path = os.path.join(input_dir, get_stored_path(initial_filename))
    with open(stored_path, write_mode) as out_file:
        out_file.write(file_data)

    tus_write_file_metadata(stored_path, initial_filename, None)
    return stored_path


def copy_uploaded_file(
    input_dir, input_filename, trans_dir, output_filename, write_mode='wb'
):
    if isinstance(input_dir, str):
        input_file_path = os.path.join(input_dir, input_filename)
        with open(input_file_path, 'rb') as in_file:
            return write_uploaded_file(
                output_filename, trans_dir, in_file.read(), write_mode
            )
    else:
        input_file_path = input_dir / input_filename
        with input_file_path.open('rb') as in_file:
            return write_uploaded_file(
                output_filename, trans_dir, in_file.read(), write_mode
            )


def cleanup(request, func):
    def inner():
        try:
            func()
        except:  # noqa
            pass

    request.addfinalizer(inner)


def get_elasticsearch_status(flask_app_client, user, expected_status_code=200):
    from app.extensions import elasticsearch as es

    if not is_extension_enabled('elasticsearch'):
        return {}

    if es.is_disabled():
        return {}

    response = get_dict_via_flask(
        flask_app_client,
        user,
        scopes='search:read',
        path='/api/v1/search/status',
        expected_status_code=expected_status_code,
        response_200=None,
    )
    status = response.json

    return status


def wait_for_celery_task(task_id):
    # from app.utils import get_celery_tasks_scheduled
    from app.utils import get_celery_data

    trial = 6
    while trial > 0:
        data = get_celery_data(task_id)
        if data and data[0]:
            return
        time.sleep(2)
        trial -= 1


def wait_for_elasticsearch_status(flask_app_client, user, force=True):
    from app.extensions import elasticsearch as es

    log = logging.getLogger('elasticsearch')  # pylint: disable=invalid-name

    trial = 0
    status = {}
    while True:
        with es.session.begin(blocking=True, forced=force, verify=True):
            es.es_index_all()

        try:
            status = get_elasticsearch_status(flask_app_client, user)
        except json.decoder.JSONDecodeError:
            status = {'error': 'decoding problem'}
        log.info('Elasticsearch status: {}'.format(status))

        # Remove any outdated, disabled, health flags
        remove_keys = [
            'elasticsearch:enabled',
            'status',
        ]
        keys = list(status.keys())
        for key in keys:
            if key.endswith(':outdated') or key in remove_keys:
                status.pop(key, None)

        if len(status) == 0:
            break

        if trial > 10:
            raise RuntimeError()

        trial += 1
        time.sleep(1)


def wait_for_progress(flask_app, progress_guids=None):
    from app.modules.progress.models import Progress

    if progress_guids is None:
        progress_guids = []

    trial = 0
    while True:
        try:
            # Fetch the detection results from Sage
            pending = flask_app.sage.sync_jobs()
            if pending == 0:
                break

            for progress_guid in progress_guids:
                progress = Progress.query.get(progress_guid)
                if progress:
                    assert not progress.active
                    assert progress.complete

            break
        except AssertionError:
            pass

        if trial > 300:
            raise RuntimeError('Failed to get all progress trackers completed')

        trial += 1
        time.sleep(1)


def elasticsearch(flask_app_client, user, namespace, data=None, expected_status_code=200):
    if data is None:
        data = {}

    scope = '{}:read'.format(namespace)
    with flask_app_client.login(user, auth_scopes=(scope,)):
        response = flask_app_client.post(
            '/api/v1/{}/search/'.format(namespace),
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        validate_list_response(response, 200)
    else:
        validate_dict_response(response, expected_status_code, {'status', 'message'})
    return response


def get_region_ids():
    from tests.conftest import test_config

    if 'regions' in test_config:
        return [loc['id'] for loc in test_config['regions']]
    return []


def get_valid_location_id(index=0):
    return get_region_ids()[index]
