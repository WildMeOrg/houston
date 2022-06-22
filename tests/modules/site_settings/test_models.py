# -*- coding: utf-8 -*-
import uuid
from pathlib import Path

import pytest

from app.modules.fileuploads.models import FileUpload
from app.modules.site_settings.models import SiteSetting
from tests.utils import extension_unavailable, is_extension_enabled


def test_create_header_image(db, flask_app, test_root):
    fup = FileUpload.create_fileupload_from_path(str(test_root / 'zebra.jpg'), copy=True)
    fup2 = FileUpload.create_fileupload_from_path(str(test_root / 'fluke.jpg'), copy=True)
    with db.session.begin():
        db.session.add(fup)
        db.session.add(fup2)
    prev_site_settings = SiteSetting.query.count()
    header_image = SiteSetting.set(key='header_image', file_upload_guid=fup.guid)
    try:
        assert (
            repr(header_image)
            == f"<SiteSetting(key='header_image' file_upload_guid='{fup.guid}' public=True)>"
        )
        # Set header image again
        SiteSetting.set(key='header_image', file_upload_guid=fup2.guid)
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
    new_setting = SiteSetting.set(key='email_title_greeting', string='Hello')
    try:
        read_value = SiteSetting.query.get('email_title_greeting')
        assert read_value.string == 'Hello'

    finally:
        db.session.delete(new_setting)


@pytest.mark.skipif(
    extension_unavailable('intelligent_agent'),
    reason='intelligent_agent extension disabled',
)
def test_boolean(db):
    bkey = 'intelligent_agent_twitterbot_enabled'
    old_value = SiteSetting.get_value(bkey)
    new_setting = SiteSetting.set(key=bkey, boolean=False)
    try:
        read_value = SiteSetting.query.get(bkey)
        assert read_value.boolean is False
        read_value = SiteSetting.get_value(bkey)
        assert read_value is False

        SiteSetting.set(key=bkey, boolean=True)
        read_value = SiteSetting.query.get(bkey)
        assert read_value.boolean is True
        read_value = SiteSetting.get_value(bkey)
        assert read_value is True

        SiteSetting.set(key=bkey, boolean=None)
        read_value = SiteSetting.query.get(bkey)
        assert read_value.boolean is None
        read_value = SiteSetting.get_value(bkey)
        assert read_value is None

    finally:
        if old_value:
            SiteSetting.set(key=bkey, boolean=old_value)
        else:
            db.session.delete(new_setting)


def test_get_value(db, flask_app):
    if is_extension_enabled('edm'):
        # Make sure site.name is set in edm
        flask_app.edm.request_passthrough(
            'configuration.data',
            'post',
            {'json': {'site.name': 'My test site'}},
            '',
            target='default',
        )
    # this should grab from edm and return a string
    val = SiteSetting.get_value('site.name')
    if is_extension_enabled('edm'):
        assert isinstance(val, str)
    else:
        assert val is None

    guid = SiteSetting.get_system_guid()
    uuid.UUID(guid, version=4)  # will throw ValueError if not a uuid
    assert guid == SiteSetting.get_value('system_guid')
    # just for kicks lets test this too
    assert guid == SiteSetting.get_string('system_guid')
    guid_setting = SiteSetting.query.get('system_guid')
    assert guid_setting is not None
    db.session.delete(guid_setting)


@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
def test_read_edm_configuration(flask_app):
    flask_app.edm.request_passthrough(
        'configuration.data',
        'post',
        {'json': {'site.name': 'My test site'}},
        '',
        target='default',
    )
    block_config_data = SiteSetting._get_edm_rest_data()['response']['configuration']
    assert isinstance(block_config_data['site.name']['value'], str)
    species_ = block_config_data.get('site.species')
    species = None
    if species_ and 'value' in species_:
        species = species_['value']
    if species is None:
        flask_app.edm.request_passthrough(
            'configuration.data',
            'post',
            {
                'json': {
                    'site.species': [
                        {'commonNames': ['Example'], 'scientificName': 'Exempli gratia'}
                    ]
                }
            },
            '',
            target='default',
        )
        block_config_data = SiteSetting._get_edm_definitions()['response'][
            'configuration'
        ]
        species = block_config_data.get('site.species')['value']

    assert isinstance(species, list)
    with pytest.raises(ValueError):
        SiteSetting.get_value('_fu_bar_')
