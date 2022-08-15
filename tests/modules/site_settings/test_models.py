# -*- coding: utf-8 -*-
import uuid
from pathlib import Path

import pytest

from app.modules.fileuploads.models import FileUpload
from app.modules.site_settings.models import SiteSetting
from tests.utils import extension_unavailable


def test_create_header_image(db, flask_app, test_root):
    fup = FileUpload.create_fileupload_from_path(str(test_root / 'zebra.jpg'), copy=True)
    fup2 = FileUpload.create_fileupload_from_path(str(test_root / 'fluke.jpg'), copy=True)
    with db.session.begin():
        db.session.add(fup)
        db.session.add(fup2)
    prev_site_settings = SiteSetting.query.count()
    header_image = SiteSetting.set_key_value('logo', fup.guid)

    try:
        assert (
            repr(header_image)
            == f"<SiteSetting(key='logo' file_upload_guid='{fup.guid}' public=True)>"
        )
        # Set header image again
        SiteSetting.set_key_value('logo', fup2.guid)
        assert SiteSetting.query.count() == prev_site_settings + 1
    finally:
        db.session.delete(header_image)
        fup.delete()
        # The fileupload object should be deleted already
        assert FileUpload.query.filter(FileUpload.guid == fup2.guid).first() is None
        file_path = Path(fup2.get_absolute_path())
        if file_path.exists():
            file_path.unlink()


def test_create_string(db):
    key = 'email_title_greeting'
    new_setting = SiteSetting.set_key_value(key, 'Hello')
    try:
        assert new_setting.string == 'Hello'
    finally:
        db.session.delete(new_setting)


@pytest.mark.skipif(
    extension_unavailable('intelligent_agent'),
    reason='intelligent_agent extension disabled',
)
def test_boolean(db):
    bkey = 'intelligent_agent_twitterbot_enabled'
    old_value = SiteSetting.get_value(bkey)
    SiteSetting.set_key_value(bkey, False)
    new_setting = SiteSetting.query.get(bkey)
    try:
        read_value = SiteSetting.query.get(bkey)
        assert read_value.boolean is False
        read_value = SiteSetting.get_value(bkey)
        assert read_value is False

        SiteSetting.set_key_value(bkey, True)
        read_value = SiteSetting.query.get(bkey)
        assert read_value.boolean is True
        read_value = SiteSetting.get_value(bkey)
        assert read_value is True

    finally:
        if old_value:
            SiteSetting.set_key_value(bkey, old_value)
        else:
            db.session.delete(new_setting)


def test_get_value(db, flask_app):
    guid = SiteSetting.get_system_guid()
    uuid.UUID(guid, version=4)  # will throw ValueError if not a uuid
    assert guid == SiteSetting.get_value('system_guid')
    guid_setting = SiteSetting.query.get('system_guid')
    assert guid_setting is not None
    db.session.delete(guid_setting)
