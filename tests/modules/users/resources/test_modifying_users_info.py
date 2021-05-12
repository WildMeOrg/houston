# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import io
import json
from pathlib import Path
import shutil
import tempfile
import uuid

from app.modules.users.models import User
from app.modules.fileuploads.models import FileUpload
from PIL import Image

from tests.utils import TemporaryDirectoryGraceful


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
                        {'op': 'replace', 'path': '/is_staff', 'value': False},
                        {'op': 'replace', 'path': '/is_admin', 'value': True},
                        {'op': 'replace', 'path': '/is_contributor', 'value': True},
                        {'op': 'replace', 'path': '/is_researcher', 'value': True},
                        {'op': 'replace', 'path': '/is_user_manager', 'value': True},
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
    finally:
        # Restore original state
        regular_user.full_name = saved_full_name
        regular_user.is_active = True
        regular_user.is_staff = False
        regular_user.is_admin = False
        regular_user.is_researcher = False
        regular_user.is_contributor = False
        regular_user.is_user_manager = False
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
                        {'op': 'replace', 'path': '/is_staff', 'value': False},
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

    with (test_root / 'zebra.jpg').open('rb') as f:
        zebra = f.read()

    def cleanup_fileupload_dir(path):
        for c in path.glob('*'):
            child = Path(c)
            if child.is_dir():
                cleanup_fileupload_dir(child)
                if not list(child.glob('*')):
                    child.rmdir()

    def cleanup():
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
        with TemporaryDirectoryGraceful() as td:
            testfile = Path(td) / 'a.txt'
            with testfile.open('w') as f:
                f.write('abcd\n')
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
        transaction_id = td.name[len('trans-') :]
        with (td / 'image.jpg').open('wb') as f:
            f.write(zebra)
        with (td / 'a.txt').open('w') as f:
            f.write('abcd')
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
        transaction_id = td.name[len('trans-') :]
        with (td / 'image.jpg').open('wb') as f:
            f.write(zebra)
        with (td / 'a.txt').open('w') as f:
            f.write('abcd')
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
        assert src_data == zebra
        clean_up_objects.append(fup)
        clean_up_paths.append(td)

        # PATCH replace /profile_fileupload_guid with transaction_id
        td = Path(tempfile.mkdtemp(prefix='trans-', dir=upload_dir))
        transaction_id = td.name[len('trans-') :]
        with (td / 'image.jpg').open('wb') as f:
            f.write(zebra)
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
        with TemporaryDirectoryGraceful() as td:
            testfile = Path(td) / 'image.jpg'
            with testfile.open('wb') as f:
                f.write(zebra)
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

        # Create non image fileupload
        with TemporaryDirectoryGraceful() as td:
            testfile = Path(td) / 'a.txt'
            with testfile.open('w') as f:
                f.write('abcd\n')
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
