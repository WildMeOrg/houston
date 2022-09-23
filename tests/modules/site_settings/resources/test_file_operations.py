# -*- coding: utf-8 -*-
from pathlib import Path

import pytest
import utils as site_setting_utils

from app.modules.fileuploads.models import FileUpload
from app.modules.site_settings.models import SiteSetting
from tests.utils import (
    TemporaryDirectoryUUID,
    copy_uploaded_file,
    module_unavailable,
    write_uploaded_file,
)


def setup_logo(db, test_root, request):
    zebra_path = test_root / 'zebra.jpg'
    fup = FileUpload.create_fileupload_from_path(str(zebra_path), copy=True)
    with db.session.begin():
        db.session.add(fup)
    request.addfinalizer(lambda: fup.delete())
    logo_image = SiteSetting.set_key_value('logo', fup.guid)
    request.addfinalizer(lambda: db.session.delete(logo_image))


@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
def test_file_settings(admin_user, flask_app_client, flask_app, db, request, test_root):
    setup_logo(db, test_root, request)

    # Get image without logging inn (in the way that the FE does it)
    block = site_setting_utils.read_main_settings(flask_app_client, None).json
    logo_path = block['site.images']['logo']
    resp = flask_app_client.get(logo_path)
    assert resp.status_code == 200
    assert resp.content_type == 'image/jpeg'
    resp.close()

    upload_dir = flask_app.config['UPLOADS_DATABASE_PATH']

    with TemporaryDirectoryUUID(prefix='trans-', dir=upload_dir) as td:
        transaction_id = Path(td).name[len('trans-') :]
        copy_uploaded_file(test_root, 'zebra.jpg', Path(td), 'image.jpg')

        splash_image_data = site_setting_utils.modify_main_settings(
            flask_app_client, admin_user, {'transactionId': transaction_id}, 'splashImage'
        ).json
        assert splash_image_data['key'] == 'splashImage'
        filename_guid = splash_image_data['value']

        splash_read = site_setting_utils.read_main_settings(
            flask_app_client, admin_user, 'splashImage'
        ).json
        assert splash_read['key'] == 'splashImage'
        assert splash_read['value'] == filename_guid

    # Edit site setting using transactionId with 2 files
    with TemporaryDirectoryUUID(prefix='trans-', dir=upload_dir) as td:
        transaction_id = Path(td).name[len('trans-') :]
        write_uploaded_file('a.txt', Path(td), '1234')
        write_uploaded_file('b.txt', Path(td), '5678')
        resp = site_setting_utils.modify_main_settings(
            flask_app_client, admin_user, {'transactionId': transaction_id}, 'logo', 422
        ).json
        assert (
            resp['message']
            == f'Transaction {transaction_id} has 2 files, need exactly 1.'
        )

    # Edit site setting using transactionId and transactionPath
    with TemporaryDirectoryUUID(prefix='trans-', dir=upload_dir) as td:
        transaction_id = Path(td).name[len('trans-') :]
        write_uploaded_file('a.txt', Path(td), '1234')
        file_data = {
            'transactionId': transaction_id,
            'transactionPath': 'a.txt',
        }
        resp = site_setting_utils.modify_main_settings(
            flask_app_client, admin_user, file_data, 'logo'
        ).json

        assert resp['key'] == 'logo'

    # Delete site setting
    site_setting_utils.delete_main_setting(flask_app_client, admin_user, 'logo')
    site_setting_utils.delete_main_setting(flask_app_client, admin_user, 'splashImage')


@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
def test_file_setting_block(
    admin_user, flask_app_client, flask_app, db, request, test_root
):
    upload_dir = flask_app.config['UPLOADS_DATABASE_PATH']
    # Edit site setting using transactionId and transactionPath as a post with other site setting data
    with TemporaryDirectoryUUID(prefix='trans-', dir=upload_dir) as td:
        transaction_id = Path(td).name[len('trans-') :]
        write_uploaded_file('a.txt', Path(td), '1234')
        data = {
            'splashImage': {
                'transactionId': transaction_id,
                'transactionPath': 'a.txt',
            },
            'site.general.tagline': 'This is a tagline',
        }
        site_setting_utils.modify_main_settings(flask_app_client, admin_user, data)


@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
def test_site_settings_permissions(
    regular_user, flask_app_client, flask_app, db, request, test_root
):
    setup_logo(db, test_root, request)

    upload_dir = flask_app.config['UPLOADS_DATABASE_PATH']
    with TemporaryDirectoryUUID(prefix='trans-', dir=upload_dir) as td:
        transaction_id = Path(td).name[len('trans-') :]
        copy_uploaded_file(test_root, 'zebra.jpg', Path(td), 'image.jpg')

        # Regular user cannot write images
        site_setting_utils.modify_main_settings(
            flask_app_client,
            regular_user,
            {'transactionId': transaction_id},
            'splashImage',
            403,
        )
        site_setting_utils.modify_main_settings(
            flask_app_client, regular_user, {'transactionId': transaction_id}, 'logo', 403
        )

        # or delete them
        site_setting_utils.delete_main_setting(flask_app_client, regular_user, 'logo', 403)
