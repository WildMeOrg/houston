# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

import pytest

from app.modules.site_settings.models import SiteSetting
from tests.modules.site_settings.resources import utils as conf_utils
from tests.utils import extension_unavailable, module_unavailable

BUNDLE_PATH = 'block'


@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
def test_bundle_read(flask_app_client, admin_user):
    response = conf_utils.read_main_settings(flask_app_client, admin_user)
    assert response.json['success']
    assert response.json['response']
    assert 'configuration' in response.json['response']
    assert isinstance(response.json['response']['configuration'], dict)
    assert 'site.name' in response.json['response']['configuration']
    assert 'value' in response.json['response']['configuration']['site.name']
    assert response.json['response']['configuration']['site.name'] is not None


@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-Settings module disabled'
)
def test_bundle_modify(flask_app_client, admin_user, db):
    response = conf_utils.read_main_settings(flask_app_client, admin_user)
    orig_name = response.json['response']['configuration']['site.name']['value']
    key = 'site.name'
    test_value = 'TEST-' + str(uuid.uuid4())
    data = {
        key: test_value,
    }
    response = conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        data,
    )
    assert response.json['success']
    assert response.json['updated']
    assert isinstance(response.json['updated'], list)
    assert key in response.json['updated']
    # bonus test of SiteSetting read (of edm conf)
    assert SiteSetting.get_value(key) == test_value

    # test SiteSetting modification via bundle
    #   first a failure (invalid value of valid key)
    key = 'email_default_sender_name'
    data = {
        'bad_key': 'abcd',  # this should be ignored
        key: {'foo': 'bar'},  # this should cause a 400
    }
    response = conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        data,
        expected_status_code=400,
    )
    assert key in response.json['message']  # error message

    #   now this should work
    key2 = 'site.name'
    data = {
        'bad_key': 'abcd',  # this should be ignored
        key: test_value,
        key2: orig_name,
    }
    response = conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        data,
    )
    assert response.json['success']
    assert response.json['updated']
    assert isinstance(response.json['updated'], list)
    assert key in response.json['updated']
    assert key2 in response.json['updated']
    # get_string since this is SiteSetting
    assert SiteSetting.get_string(key) == test_value
    # get_value since this is edm conf value
    assert SiteSetting.get_value(key2) == orig_name

    # cleanup
    setting = SiteSetting.query.get(key)
    assert setting is not None
    db.session.delete(setting)
