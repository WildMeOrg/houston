# -*- coding: utf-8 -*-
from pathlib import Path
import tempfile

from app.modules.fileuploads.models import FileUpload
from app.modules.site_settings.models import SiteSetting


def test_site_settings(admin_user, flask_app_client, flask_app, db, request):
    project_root = Path(flask_app.config['PROJECT_ROOT'])
    zebra_path = project_root / 'tests/submissions/test-000/zebra.jpg'
    fup = FileUpload.create_fileupload_from_path(str(zebra_path), copy=True)
    with db.session.begin():
        db.session.add(fup)
    request.addfinalizer(lambda: fup.delete())
    header_image = SiteSetting.set('header_image', fup.guid)
    request.addfinalizer(lambda: db.session.delete(header_image))

    # Get site setting without logging in
    resp = flask_app_client.get('/api/v1/site-settings/header_image')
    assert resp.status_code == 302
    resp = flask_app_client.get(resp.location)
    assert resp.status_code == 200
    assert resp.content_type == 'image/jpeg'
    resp.close()

    # Get non public setting without logging in
    SiteSetting.set('not_public', fup.guid, public=False)
    resp = flask_app_client.get('/api/v1/site-settings/not_public')
    assert resp.status_code == 403

    with flask_app_client.login(
        admin_user, auth_scopes=('site-settings:read', 'site-settings:write')
    ):
        # Create site setting
        resp = flask_app_client.post(
            '/api/v1/site-settings/',
            data={
                'key': 'footer_image',
                'file_upload_guid': str(fup.guid),
            },
        )
        assert resp.status_code == 200
        site_setting = resp.json
        assert site_setting['key'] == 'footer_image'

        # List site settings
        resp = flask_app_client.get('/api/v1/site-settings/')
        assert resp.status_code == 200
        assert resp.json == [
            {'key': 'footer_image', 'file_upload_guid': str(fup.guid), 'public': True},
            {'key': 'header_image', 'file_upload_guid': str(fup.guid), 'public': True},
            {'key': 'not_public', 'file_upload_guid': str(fup.guid), 'public': False},
        ]

        # Edit site setting
        resp = flask_app_client.post(
            '/api/v1/site-settings/',
            data={
                'key': 'header_image',
                'file_upload_guid': str(fup.guid),
            },
        )
        assert resp.status_code == 200
        site_setting = resp.json
        assert site_setting['key'] == 'header_image'

        # Edit site setting using transactionId
        upload_dir = flask_app.config['UPLOADS_DATABASE_PATH']
        with tempfile.TemporaryDirectory(prefix='trans-', dir=upload_dir) as td:
            transaction_id = Path(td).name[len('trans-') :]

            with (Path(td) / 'image.jpg').open('wb') as f:
                with zebra_path.open('rb') as g:
                    f.write(g.read())
            resp = flask_app_client.post(
                '/api/v1/site-settings/',
                data={
                    'key': 'header_image',
                    'transactionId': transaction_id,
                },
            )
            assert resp.status_code == 200, resp.data
            assert resp.json['key'] == 'header_image'
            assert resp.json['file_upload_guid'] != str(fup.guid)

        # Edit site setting using transactionId with 2 files
        with tempfile.TemporaryDirectory(prefix='trans-', dir=upload_dir) as td:
            transaction_id = Path(td).name[len('trans-') :]
            with (Path(td) / 'a.txt').open('w') as f:
                f.write('1234')
            with (Path(td) / 'b.txt').open('w') as f:
                f.write('5678')
            resp = flask_app_client.post(
                '/api/v1/site-settings/',
                data={
                    'key': 'header_image',
                    'transactionId': transaction_id,
                },
            )
            assert resp.status_code == 422
            assert (
                resp.json['message']
                == f'Transaction {transaction_id} has 2 files, need exactly 1.'
            )

        # Edit site setting using transactionId and transactionPath
        with tempfile.TemporaryDirectory(prefix='trans-', dir=upload_dir) as td:
            transaction_id = Path(td).name[len('trans-') :]
            with (Path(td) / 'a.txt').open('w') as f:
                f.write('1234')
            with (Path(td) / 'b.txt').open('w') as f:
                f.write('5678')
            resp = flask_app_client.post(
                '/api/v1/site-settings/',
                data={
                    'key': 'header_image',
                    'transactionId': transaction_id,
                    'transactionPath': 'a.txt',
                },
            )
            assert resp.status_code == 200
            assert resp.json['key'] == 'header_image'

        # Delete site setting
        resp = flask_app_client.delete('/api/v1/site-settings/header_image')
        assert resp.status_code == 204
        resp = flask_app_client.delete('/api/v1/site-settings/footer_image')
        assert resp.status_code == 204

        # List site settings
        resp = flask_app_client.get('/api/v1/site-settings/')
        assert resp.status_code == 200
        assert resp.json == []


def test_site_settings_permissions(
    regular_user, flask_app_client, flask_app, db, request
):
    project_root = Path(flask_app.config['PROJECT_ROOT'])
    zebra_path = project_root / 'tests/submissions/test-000/zebra.jpg'
    fup = FileUpload.create_fileupload_from_path(str(zebra_path), copy=True)
    with db.session.begin():
        db.session.add(fup)
    request.addfinalizer(lambda: fup.delete())
    header_image = SiteSetting.set('header_image', fup.guid)
    request.addfinalizer(lambda: db.session.delete(header_image))

    with flask_app_client.login(
        regular_user, auth_scopes=('site-settings:read', 'site-settings:write')
    ):
        # Create site setting
        resp = flask_app_client.post(
            '/api/v1/site-settings/',
            data={
                'key': 'footer_image',
                'file_upload_guid': str(fup.guid),
            },
        )
        assert resp.status_code == 403

        # Edit site setting
        resp = flask_app_client.post(
            '/api/v1/site-settings/',
            data={
                'key': 'header_image',
                'file_upload_guid': str(fup.guid),
            },
        )
        assert resp.status_code == 403

        # List site settings
        resp = flask_app_client.get('/api/v1/site-settings/')
        assert resp.status_code == 403

        # Delete site setting
        resp = flask_app_client.delete('/api/v1/site-settings/header_image')
        assert resp.status_code == 403
