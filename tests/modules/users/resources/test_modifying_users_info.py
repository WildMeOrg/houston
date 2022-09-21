# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import io
import json
import shutil
import tempfile
import uuid
from pathlib import Path

from PIL import Image

import tests.modules.users.resources.utils as user_utils
from app.modules.fileuploads.models import FileUpload
from app.modules.users.models import User
from flask_restx_patched import is_extension_enabled
from tests.utils import TemporaryDirectoryUUID, copy_uploaded_file, write_uploaded_file


def test_user_id_not_found(flask_app_client, regular_user):
    with flask_app_client.login(
        regular_user,
        auth_scopes=(
            'users:read',
            'users:write',
        ),
    ):
        response = flask_app_client.patch(
            '/api/v1/users/wrong-uuid',
            content_type='application/json',
            data=json.dumps(
                [
                    {
                        'op': 'replace',
                        'path': '/full_name',
                        'value': 'Modified Full Name',
                    }
                ]
            ),
        )
        assert response.status_code == 404
        response.close()


def test_modifying_user_info_by_owner(flask_app_client, regular_user, db):
    # pylint: disable=invalid-name
    saved_full_name = regular_user.full_name
    try:
        with flask_app_client.login(regular_user, auth_scopes=('users:write',)):
            response = flask_app_client.patch(
                '/api/v1/users/%s' % regular_user.guid,
                content_type='application/json',
                data=json.dumps(
                    [
                        {
                            'op': 'test',
                            'path': '/current_password',
                            'value': regular_user.password_secret,
                        },
                        {
                            'op': 'replace',
                            'path': '/full_name',
                            'value': 'Modified Full Name',
                        },
                    ]
                ),
            )

        temp_user = User.query.get(response.json['guid'])

        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert isinstance(response.json, dict)
        assert set(response.json.keys()) >= {'guid', 'email'}
        assert uuid.UUID(response.json['guid']) == regular_user.guid
        assert 'password' not in response.json.keys()

        assert temp_user.email == regular_user.email
        assert temp_user.full_name == 'Modified Full Name'
    finally:
        # Restore original state
        regular_user.full_name = saved_full_name
        with db.session.begin():
            db.session.merge(regular_user)


def test_modifying_user_info_by_admin(flask_app_client, admin_user, regular_user, db):
    # pylint: disable=invalid-name
    saved_full_name = regular_user.full_name
    try:
        with flask_app_client.login(admin_user, auth_scopes=('users:write',)):
            response = flask_app_client.patch(
                '/api/v1/users/%s' % regular_user.guid,
                content_type='application/json',
                data=json.dumps(
                    [
                        {
                            'op': 'test',
                            'path': '/current_password',
                            'value': admin_user.password_secret,
                        },
                        {
                            'op': 'replace',
                            'path': '/full_name',
                            'value': 'Modified Full Name',
                        },
                        {'op': 'replace', 'path': '/is_active', 'value': False},
                        {'op': 'replace', 'path': '/is_admin', 'value': True},
                        {'op': 'replace', 'path': '/is_contributor', 'value': True},
                        {'op': 'replace', 'path': '/is_researcher', 'value': True},
                        {'op': 'replace', 'path': '/is_user_manager', 'value': True},
                        {'op': 'replace', 'path': '/is_exporter', 'value': True},
                        {'op': 'replace', 'path': '/password', 'value': 'NEW_PASSWORD'},
                    ]
                ),
            )

        from app.modules.users.models import User

        temp_user = User.query.get(response.json['guid'])
        assert temp_user.is_researcher
        assert temp_user.is_contributor
        assert temp_user.is_user_manager
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert isinstance(response.json, dict)
        assert set(response.json.keys()) >= {'guid', 'email'}
        assert uuid.UUID(response.json['guid']) == regular_user.guid
        assert 'password' not in response.json.keys()

        assert temp_user.email == regular_user.email
        assert temp_user.full_name == 'Modified Full Name'
        assert not temp_user.is_active
        assert not temp_user.is_staff
        assert temp_user.is_admin
        assert not temp_user.is_internal
        assert temp_user.is_exporter
        assert temp_user.password == 'NEW_PASSWORD'
    finally:
        # Restore original state
        regular_user.full_name = saved_full_name
        regular_user.is_active = True
        regular_user.is_staff = False
        regular_user.is_admin = False
        regular_user.is_researcher = False
        regular_user.is_contributor = False
        regular_user.is_user_manager = False
        regular_user.password = regular_user.password_secret
        with db.session.begin():
            db.session.merge(regular_user)


def test_invalid_modifying_user_info_by_admin(
    flask_app_client, admin_user, regular_user, db
):
    # pylint: disable=invalid-name
    data = [
        {
            'op': 'test',
            'path': '/current_password',
            'value': admin_user.password_secret,
        },
        {'op': 'replace', 'path': '/is_staff', 'value': True},
    ]
    error = 'The request was formatted correctly but contains a semantic error (check input values and types).'
    user_utils.patch_user(flask_app_client, admin_user, regular_user, data, 422, error)

    data = [
        {
            'op': 'test',
            'path': '/current_password',
            'value': admin_user.password_secret,
        },
        {'op': 'replace', 'path': '/is_internal', 'value': True},
    ]

    user_utils.patch_user(flask_app_client, admin_user, regular_user, data, 422, error)


def test_modifying_email_addr(flask_app_client, regular_user, admin_user, db):
    # Test a garbage one
    data = [
        {
            'op': 'test',
            'path': '/current_password',
            'value': regular_user.password_secret,
        },
        {'op': 'replace', 'path': '/email', 'value': 'invalidemailaddress'},
    ]
    error = 'Not a valid email address.'
    user_utils.patch_user(flask_app_client, regular_user, regular_user, data, 422, error)

    data = [
        {
            'op': 'test',
            'path': '/current_password',
            'value': regular_user.password_secret,
        },
        {'op': 'replace', 'path': '/email', 'value': admin_user.email},
    ]
    error = 'Email address already in use'
    user_utils.patch_user(flask_app_client, regular_user, regular_user, data, 422, error)
    data = [
        {
            'op': 'test',
            'path': '/current_password',
            'value': regular_user.password_secret,
        },
        {'op': 'replace', 'path': '/email', 'value': regular_user.email},
    ]
    user_utils.patch_user(flask_app_client, regular_user, regular_user, data)


def test_modifying_password(flask_app_client, regular_user, user_manager_user, db):
    # pylint: disable=invalid-name
    test_password = 'TEST_NEW_PASSWORD'
    try:
        # should fail: regular user changing password of manager user
        with flask_app_client.login(regular_user, auth_scopes=('users:write',)):
            response = flask_app_client.patch(
                '/api/v1/users/%s' % user_manager_user.guid,
                content_type='application/json',
                data=json.dumps(
                    [
                        {
                            'op': 'test',
                            'path': '/current_password',
                            'value': regular_user.password_secret,
                        },
                        {
                            'op': 'replace',
                            'path': '/password',
                            'value': test_password,
                        },
                    ]
                ),
            )

        assert response.status_code == 403
        assert response.content_type == 'application/json'
        assert isinstance(response.json, dict)
        assert set(response.json.keys()) >= {'status', 'message'}
        temp_user = User.query.get(user_manager_user.guid)
        assert not temp_user.password == test_password
    finally:
        user_manager_user.password = user_manager_user.password_secret
        with db.session.begin():
            db.session.merge(user_manager_user)

    try:
        # should succeed: manager user changing user password
        with flask_app_client.login(user_manager_user, auth_scopes=('users:write',)):
            response = flask_app_client.patch(
                '/api/v1/users/%s' % regular_user.guid,
                content_type='application/json',
                data=json.dumps(
                    [
                        {
                            'op': 'test',
                            'path': '/current_password',
                            'value': user_manager_user.password_secret,
                        },
                        {
                            'op': 'replace',
                            'path': '/password',
                            'value': test_password,
                        },
                    ]
                ),
            )

        assert response.status_code == 200
        temp_user = User.query.get(regular_user.guid)
        assert temp_user.password == test_password
    finally:
        regular_user.password = regular_user.password_secret
        with db.session.begin():
            db.session.merge(regular_user)


def test_modifying_user_info_admin_fields_by_not_admin(
    flask_app_client, regular_user, db
):
    # pylint: disable=invalid-name
    saved_full_name = regular_user.full_name
    try:
        with flask_app_client.login(regular_user, auth_scopes=('users:write',)):
            response = flask_app_client.patch(
                '/api/v1/users/%s' % regular_user.guid,
                content_type='application/json',
                data=json.dumps(
                    [
                        {
                            'op': 'test',
                            'path': '/current_password',
                            'value': regular_user.password_secret,
                        },
                        {
                            'op': 'replace',
                            'path': '/full_name',
                            'value': 'Modified Full Name',
                        },
                        {'op': 'replace', 'path': '/is_active', 'value': False},
                        {'op': 'replace', 'path': '/is_admin', 'value': True},
                    ]
                ),
            )

        assert response.status_code == 403
        assert response.content_type == 'application/json'
        assert isinstance(response.json, dict)
        assert set(response.json.keys()) >= {'status', 'message'}
    finally:
        regular_user.full_name = saved_full_name
        regular_user.is_active = True
        regular_user.is_staff = False
        regular_user.is_admin = False
        with db.session.begin():
            db.session.merge(regular_user)


def test_modifying_user_info_with_invalid_format_must_fail(
    flask_app_client, regular_user
):
    # pylint: disable=invalid-name
    with flask_app_client.login(regular_user, auth_scopes=('users:write',)):
        response = flask_app_client.patch(
            '/api/v1/users/%s' % regular_user.guid,
            content_type='application/json',
            data=json.dumps(
                [
                    {'op': 'test', 'path': '/full_name', 'value': ''},
                    {'op': 'replace', 'path': '/website'},
                ]
            ),
        )

    assert response.status_code == 422
    assert response.content_type == 'application/json'
    assert isinstance(response.json, dict)
    assert set(response.json.keys()) >= {'status', 'message'}


def test_modifying_user_info_with_misformatted_data_must_fail(
    flask_app_client, regular_user
):
    with flask_app_client.login(regular_user, auth_scopes=('users:write',)):
        response = flask_app_client.patch(
            '/api/v1/users/%s' % regular_user.guid,
            content_type='application/json',
            data=json.dumps(
                [
                    {
                        'op': 'remove',
                        'path': '/profile_fileupload_guid',
                    },
                ],
            ),
        )
        assert response.status_code == 200, response.data

    # pylint: disable=invalid-name
    with flask_app_client.login(regular_user, auth_scopes=('users:write',)):
        response = flask_app_client.patch(
            '/api/v1/users/%s' % regular_user.guid,
            content_type='application/json',
            data=json.dumps(
                {'op': 'test', 'path': '/full_name', 'value': ''},
            ),
        )
        assert response.status_code == 422, response.data
        assert (
            response.json['messages']['_schema'][0]
            == 'PATCH input data must be a list of operations (JSON objects)'
        )

    with flask_app_client.login(regular_user, auth_scopes=('users:write',)):
        response = flask_app_client.patch(
            '/api/v1/users/%s' % regular_user.guid,
            content_type='application/json',
            data=json.dumps([1, 2, 3]),
        )
        assert response.status_code == 422, response.data
        assert (
            response.json['messages']['0']['_schema'][0]
            == 'Individual PATCH operations must be JSON objects'
        )

    if not is_extension_enabled('elasticsearch'):
        # Skip the rest of the test if elasticsearch is not enabled
        return

    index, guid, body = regular_user.serialize()
    with flask_app_client.login(regular_user, auth_scopes=('users:write',)):
        response = flask_app_client.patch(
            '/api/v1/users/%s' % regular_user.guid,
            content_type='application/json',
            data=json.dumps(body),
        )
        assert response.status_code == 422, response.data
        assert (
            response.json['messages']['_schema'][0]
            == 'PATCH input data must be a list of operations (JSON objects)'
        )

    with flask_app_client.login(regular_user, auth_scopes=('users:write',)):
        response = flask_app_client.patch(
            '/api/v1/users/%s' % regular_user.guid,
            content_type='application/json',
            data=json.dumps([body]),
        )
        assert response.status_code == 422, response.data
        assert response.json['messages']['0']['_schema'][0] == 'operation not supported'


def test_modifying_user_info_with_invalid_password_must_fail(
    flask_app_client, regular_user
):
    # pylint: disable=invalid-name
    with flask_app_client.login(regular_user, auth_scopes=('users:write',)):
        response = flask_app_client.patch(
            '/api/v1/users/%s' % regular_user.guid,
            content_type='application/json',
            data=json.dumps(
                [
                    {
                        'op': 'test',
                        'path': '/current_password',
                        'value': 'invalid_password',
                    },
                    {
                        'op': 'replace',
                        'path': '/full_name',
                        'value': 'Modified Full Name',
                    },
                ]
            ),
        )

    assert response.status_code == 403
    assert response.content_type == 'application/json'
    assert isinstance(response.json, dict)
    assert set(response.json.keys()) >= {'status', 'message'}


def test_modifying_user_info_with_conflict_data_must_fail(
    flask_app_client, admin_user, regular_user
):
    # pylint: disable=invalid-name
    with flask_app_client.login(regular_user, auth_scopes=('users:write',)):
        response = flask_app_client.patch(
            '/api/v1/users/%s' % regular_user.guid,
            content_type='application/json',
            data=json.dumps(
                [
                    {
                        'op': 'test',
                        'path': '/current_password',
                        'value': regular_user.password_secret,
                    },
                    {'op': 'replace', 'path': '/email', 'value': admin_user.email},
                ]
            ),
        )

    assert response.status_code == 409
    assert response.content_type == 'application/json'
    assert isinstance(response.json, dict)
    assert set(response.json.keys()) >= {'status', 'message'}


def test_user_profile_fileupload(
    db, flask_app, flask_app_client, regular_user, request, test_root
):
    clean_up_objects = []
    clean_up_paths = []
    upload_dir = Path(flask_app.config['UPLOADS_DATABASE_PATH'])
    fileupload_dir = Path(flask_app.config['FILEUPLOAD_BASE_PATH'])

    zebra_file = 'zebra.jpg'

    def cleanup_fileupload_dir(path):
        for c in path.glob('*'):
            child = Path(c)
            if child.is_dir():
                cleanup_fileupload_dir(child)
                if not list(child.glob('*')):
                    child.rmdir()

    def cleanup():
        with db.session.begin():
            regular_user.profile_fileupload_guid = None
            db.session.merge(regular_user)
            for obj in clean_up_objects:
                if hasattr(obj, 'delete'):
                    obj.delete()
                else:
                    db.session.delete(obj)
        for path in clean_up_paths:
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
        cleanup_fileupload_dir(fileupload_dir)

    request.addfinalizer(cleanup)

    with flask_app_client.login(regular_user, auth_scopes=('users:write',)):
        args = (f'/api/v1/users/{regular_user.guid}',)

        # Read the profile image, check that it's a valid image but empty
        profile_response = flask_app_client.get(
            f'/api/v1/users/{regular_user.guid}/profile_image'
        )
        assert profile_response.status_code == 200, profile_response.data
        assert profile_response.content_type == 'image/jpeg'
        assert profile_response.calculate_content_length() == 0
        profile_response.close()

        # PATCH remove /profile_upload_guid when it's not set
        kwargs = {
            'content_type': 'application/json',
            'data': json.dumps(
                [
                    {
                        'op': 'remove',
                        'path': '/profile_fileupload_guid',
                    },
                ],
            ),
        }
        response = flask_app_client.patch(*args, **kwargs)
        assert response.status_code == 200, response.data

        # Create file upload
        file_contents = 'abcd\n'
        with TemporaryDirectoryUUID() as td:
            testfile = write_uploaded_file('a.txt', Path(td), file_contents)
            fup = FileUpload.create_fileupload_from_path(str(testfile))
        with db.session.begin():
            db.session.add(fup)
        clean_up_objects += [fup]
        clean_up_paths += [Path(fup.get_absolute_path())]

        # PATCH replace /profile_fileupload_guid without dict
        kwargs = {
            'content_type': 'application/json',
            'data': json.dumps(
                [
                    {
                        'op': 'replace',
                        'path': '/profile_fileupload_guid',
                        'value': str(fup.guid),
                    },
                ],
            ),
        }
        response = flask_app_client.patch(*args, **kwargs)
        assert response.status_code == 422, response.data
        assert (
            response.json['message']
            == 'Expected {"transactionId": "..."} or {"guid": "..."}'
        )

        # PATCH replace /profile_fileupload_guid with asset.guid
        kwargs = {
            'content_type': 'application/json',
            'data': json.dumps(
                [
                    {
                        'op': 'replace',
                        'path': '/profile_fileupload_guid',
                        'value': {'guid': str(fup.guid)},
                    }
                ]
            ),
        }
        response = flask_app_client.patch(*args, **kwargs)
        assert response.status_code == 200, response.data
        assert response.json['profile_fileupload']['guid'] == str(fup.guid)
        updated_user = User.query.get(regular_user.guid)
        assert updated_user.profile_fileupload_guid == fup.guid

        # Reread profile image, should be valid now
        profile_response = flask_app_client.get(
            f'/api/v1/users/{regular_user.guid}/profile_image'
        )
        assert profile_response.status_code == 200, profile_response.data
        assert profile_response.content_type == 'image/jpeg'
        assert profile_response.get_data() == bytes(file_contents, 'ascii')
        profile_response.close()

        # Test transactionId is required when not using asset guid
        kwargs = {
            'content_type': 'application/json',
            'data': json.dumps(
                [
                    {
                        'op': 'replace',
                        'path': '/profile_fileupload_guid',
                        'value': {'submissionGuid': '1234'},
                    }
                ]
            ),
        }
        response = flask_app_client.patch(*args, **kwargs)
        assert response.status_code == 422, response.data
        assert response.json['message'] == '"transactionId" or "guid" is mandatory'

        # PATCH replace /profile_fileupload_guid with transaction_id with no assets
        td = Path(tempfile.mkdtemp(prefix='trans-', dir=upload_dir))
        transaction_id = td.name[len('trans-') :]
        kwargs = {
            'content_type': 'application/json',
            'data': json.dumps(
                [
                    {
                        'op': 'replace',
                        'path': '/profile_fileupload_guid',
                        'value': {'transactionId': transaction_id},
                    }
                ]
            ),
        }
        response = flask_app_client.patch(*args, **kwargs)
        assert response.status_code == 422, response.data
        assert response.json['message'].startswith(
            'Need exactly 1 asset but found 0 assets'
        )
        clean_up_paths.append(td)

        # PATCH replace /profile_fileupload_guid with transaction_id with 2 assets
        td = Path(tempfile.mkdtemp(prefix='trans-', dir=upload_dir))
        transaction_id = td.name[len('trans-') :]
        copy_uploaded_file(test_root, zebra_file, td, 'image.jpg')
        write_uploaded_file('a.txt', td, 'abcd')

        kwargs = {
            'content_type': 'application/json',
            'data': json.dumps(
                [
                    {
                        'op': 'replace',
                        'path': '/profile_fileupload_guid',
                        'value': {'transactionId': transaction_id},
                    }
                ]
            ),
        }
        response = flask_app_client.patch(*args, **kwargs)
        assert response.status_code == 422, response.data
        assert response.json['message'].startswith(
            'Need exactly 1 asset but found 2 assets'
        )
        clean_up_paths.append(td)

        # PATCH replace /profile_fileupload_guid with transaction_id with 2 assets with path
        td = Path(tempfile.mkdtemp(prefix='trans-', dir=upload_dir))
        transaction_id = td.name[len('trans-') :]
        copy_uploaded_file(test_root, zebra_file, td, 'image.jpg')
        write_uploaded_file(td, 'a.txt', 'abcd')

        kwargs = {
            'content_type': 'application/json',
            'data': json.dumps(
                [
                    {
                        'op': 'replace',
                        'path': '/profile_fileupload_guid',
                        'value': {'transactionId': transaction_id, 'path': 'image.jpg'},
                    }
                ]
            ),
        }
        response = flask_app_client.patch(*args, **kwargs)
        assert response.status_code == 200, response.data
        fup = FileUpload.query.get(response.json['profile_fileupload']['guid'])
        src_response = flask_app_client.get(fup.src)
        src_data = src_response.data
        src_response.close()  # h/t https://github.com/pallets/flask/issues/2468#issuecomment-517797518
        with (test_root / 'zebra.jpg').open('rb') as f:
            zebra = f.read()
            assert src_data == zebra
        clean_up_objects.append(fup)
        clean_up_paths.append(td)

        # PATCH replace /profile_fileupload_guid with transaction_id
        td = Path(tempfile.mkdtemp(prefix='trans-', dir=upload_dir))
        transaction_id = td.name[len('trans-') :]
        copy_uploaded_file(test_root, zebra_file, td, 'image.jpg')

        kwargs = {
            'content_type': 'application/json',
            'data': json.dumps(
                [
                    {
                        'op': 'replace',
                        'path': '/profile_fileupload_guid',
                        'value': {'transactionId': transaction_id},
                    }
                ]
            ),
        }
        response = flask_app_client.patch(*args, **kwargs)
        assert response.status_code == 200, response.data
        response_asset_guid = response.json['profile_fileupload']['guid']
        updated_user = User.query.get(regular_user.guid)
        assert str(updated_user.profile_fileupload_guid) == response_asset_guid
        fileupload = FileUpload.query.get(response_asset_guid)
        assert updated_user.profile_fileupload == fileupload
        assert fileupload is not None, 'FileUpload linked to user does not exist'
        clean_up_objects += [fileupload]

        # PATCH remove /profile_fileupload_guid
        kwargs = {
            'content_type': 'application/json',
            'data': json.dumps([{'op': 'remove', 'path': '/profile_fileupload_guid'}]),
        }
        response = flask_app_client.patch(*args, **kwargs)
        assert response.status_code == 200, response.data
        updated_user = User.query.get(regular_user.guid)
        assert updated_user.profile_fileupload_guid is None

        # Create file upload
        with TemporaryDirectoryUUID() as td:
            testfile = copy_uploaded_file(test_root, zebra_file, td, 'image.jpg')

            fup = FileUpload.create_fileupload_from_path(str(testfile))
        with db.session.begin():
            db.session.add(fup)
        clean_up_objects += [fup]
        clean_up_paths += [Path(fup.get_absolute_path())]

        # PATCH add /profile_fileupload_guid
        kwargs = {
            'content_type': 'application/json',
            'data': json.dumps(
                [
                    {
                        'op': 'add',
                        'path': '/profile_fileupload_guid',
                        'value': {'guid': str(fup.guid)},
                    }
                ]
            ),
        }
        response = flask_app_client.patch(*args, **kwargs)
        assert response.status_code == 200, response.data
        updated_user = User.query.get(regular_user.guid)
        assert str(updated_user.profile_fileupload_guid) == str(fup.guid)

        # PATCH add /profile_fileupload_guid with invalid crop
        kwargs = {
            'content_type': 'application/json',
            'data': json.dumps(
                [
                    {
                        'op': 'add',
                        'path': '/profile_fileupload_guid',
                        'value': {
                            'guid': str(fup.guid),
                            'crop': 'invalid',
                        },
                    }
                ]
            ),
        }
        response = flask_app_client.patch(*args, **kwargs)
        assert response.status_code == 422, response.data
        assert (
            response.json['message']
            == 'Expected {"crop": {"x": <int>, "y": <int>, "width": <int>, "height": <int>}}'
        )

        with Image.open(fup.get_absolute_path()) as image:
            assert image.size == (1000, 664)

        # PATCH add /profile_fileupload_guid with crop
        kwargs = {
            'content_type': 'application/json',
            'data': json.dumps(
                [
                    {
                        'op': 'add',
                        'path': '/profile_fileupload_guid',
                        'value': {
                            'guid': str(fup.guid),
                            'crop': {
                                'x': 650,
                                'y': 150,
                                'width': 150,
                                'height': 150,
                            },
                        },
                    }
                ]
            ),
        }
        response = flask_app_client.patch(*args, **kwargs)
        assert response.status_code == 200, response.data
        src = response.json['profile_fileupload']['src']
        response = flask_app_client.get(src)
        assert response.headers['Content-Type'] == 'image/jpeg'
        with Image.open(io.BytesIO(response.data)) as image:
            assert image.size == (150, 150)
        response.close()

        # Create non image fileupload
        with TemporaryDirectoryUUID() as td:
            testfile = write_uploaded_file('a.txt', td, 'abcd\n')

            fup = FileUpload.create_fileupload_from_path(str(testfile))
        with db.session.begin():
            db.session.add(fup)
        clean_up_objects += [fup]

        # PATCH add /profile_fileupload_guid with crop not image
        kwargs = {
            'content_type': 'application/json',
            'data': json.dumps(
                [
                    {
                        'op': 'add',
                        'path': '/profile_fileupload_guid',
                        'value': {
                            'guid': str(fup.guid),
                            'crop': {
                                'x': 650,
                                'y': 150,
                                'width': 150,
                                'height': 150,
                            },
                        },
                    }
                ]
            ),
        }
        response = flask_app_client.patch(*args, **kwargs)
        assert response.status_code == 422, response.data
        assert response.json['message'].startswith(
            'UnidentifiedImageError: cannot identify image file'
        )


# this will/should go away when proper linked_accounts is utilized
def test_modifying_user_twitter_username(
    flask_app_client, regular_user, researcher_1, db
):
    # pylint: disable=invalid-name
    test_username = 'TWITTER_TEST'
    with flask_app_client.login(regular_user, auth_scopes=('users:write',)):
        response = flask_app_client.patch(
            '/api/v1/users/%s' % regular_user.guid,
            content_type='application/json',
            data=json.dumps(
                [
                    {
                        'op': 'replace',
                        'path': '/twitter_username',
                        'value': test_username,
                    },
                ]
            ),
        )
    assert response.status_code == 200
    temp_user = User.query.get(response.json['guid'])
    assert temp_user.twitter_username == test_username

    # should fail cuz we do not allow 2 users to have same twitter_username
    with flask_app_client.login(researcher_1, auth_scopes=('users:write',)):
        response = flask_app_client.patch(
            '/api/v1/users/%s' % researcher_1.guid,
            content_type='application/json',
            data=json.dumps(
                [
                    {
                        'op': 'replace',
                        'path': '/twitter_username',
                        'value': test_username,
                    },
                ]
            ),
        )
    assert response.status_code == 409  # conflict
    temp_user = User.query.get(researcher_1.guid)
    assert not temp_user.twitter_username

    # remove twitter_username
    with flask_app_client.login(regular_user, auth_scopes=('users:write',)):
        response = flask_app_client.patch(
            '/api/v1/users/%s' % regular_user.guid,
            content_type='application/json',
            data=json.dumps(
                [
                    {
                        'op': 'remove',
                        'path': '/twitter_username',
                    },
                ]
            ),
        )

    assert response.status_code == 200
    temp_user = User.query.get(response.json['guid'])
    assert not temp_user.twitter_username
