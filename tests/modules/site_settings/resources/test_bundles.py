# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

import pytest

from app.modules.site_settings.models import SiteSetting
from tests.modules.site_settings.resources import utils as conf_utils
from tests.utils import extension_unavailable, module_unavailable

BUNDLE_PATH = 'block'


@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
@pytest.mark.parametrize(
    'keys,is_edm,user_var',
    (
        (['site.name', 'email_service'], True, 'admin_user'),
        ({'email_service': 'mailchimp'}, False, 'admin_user'),
        (
            {
                'recaptchaPublicKey': 'recaptcha-key',
                'flatfileKey': 'flatfile-key',
                'EXCLUDED': ['email_service'],
            },
            False,
            'researcher_1',
        ),
        (
            {
                'recaptchaPublicKey': 'recaptcha-key',
                'EXCLUDED': ['email_service', 'flatfileKey'],
            },
            False,
            'None',
        ),
    ),
)
def test_bundle_read(
    flask_app_client, request, admin_user, researcher_1, keys, is_edm, user_var
):
    from app.modules.site_settings.models import SiteSetting

    SiteSetting.set('recaptchaPublicKey', string='recaptcha-key')
    request.addfinalizer(lambda: SiteSetting.forget_key_value('recaptchaPublicKey'))
    SiteSetting.set('flatfileKey', string='flatfile-key')
    request.addfinalizer(lambda: SiteSetting.forget_key_value('flatfileKey'))

    response = conf_utils.read_main_settings(flask_app_client, eval(user_var))
    if extension_unavailable('edm') and is_edm:
        pytest.skip('EDM extension disabled')

    assert response.json['success']
    assert response.json['response']
    assert 'configuration' in response.json['response']
    assert isinstance(response.json['response']['configuration'], dict)

    if isinstance(keys, dict):
        for key in keys.pop('EXCLUDED', []):
            assert key not in response.json['response']['configuration']

    for key in keys:
        assert key in response.json['response']['configuration']
        assert 'value' in response.json['response']['configuration'][key]
        if isinstance(keys, dict):
            value = keys[key]
            assert response.json['response']['configuration'][key]['value'] == value
        else:
            assert response.json['response']['configuration'][key]['value'] is not None


@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-Settings module disabled'
)
@pytest.mark.parametrize(
    'data,expected_status_code,is_edm',
    (
        ({'site.name': f'TEST-{str(uuid.uuid4())}'}, 200, True),
        ({'email_default_sender_name': 'testing'}, 200, False),
        (
            {
                'bad_key': 'abcd',
                'email_default_sender_name': {'foo': 'bar'},
                'email_default_sender_email': [],
            },
            400,
            False,
        ),
        (
            {
                'bad_key': 'abcd',
                'email_default_sender_name': 'Testing',
                'site.name': f'TEST-{str(uuid.uuid4())}',
            },
            200,
            True,
        ),
        ({'sentryDsn': 'sentryDsnKey'}, 200, False),
    ),
)
def test_bundle_modify(
    flask_app_client, admin_user, db, request, data, expected_status_code, is_edm
):
    if extension_unavailable('edm') and is_edm:
        pytest.skip('EDM extension disabled')

    response = conf_utils.read_main_settings(flask_app_client, admin_user)
    old_values = {}
    invalid_key = []
    for key in data:
        old_value = response.json['response']['configuration'].get(key, {})
        if old_value:
            old_values[key] = old_value['value']
        else:
            invalid_key.append(key)
    request.addfinalizer(
        lambda: conf_utils.modify_main_settings(flask_app_client, admin_user, old_values)
    )
    response = conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        data,
        expected_status_code=expected_status_code,
    )
    if expected_status_code == 200:
        assert response.json['success']
        assert response.json['updated']
        assert isinstance(response.json['updated'], list)
        for key, value in data.items():
            if key in invalid_key:
                assert key not in response.json['updated']
                assert SiteSetting.get_value(key) is None
            else:
                assert key in response.json['updated']
                assert SiteSetting.get_value(key) == value
    else:
        for key in data:
            if key in invalid_key:
                assert key not in response.json['message']
            else:
                assert key in response.json['message']
                break  # Only the first valid key is reported
