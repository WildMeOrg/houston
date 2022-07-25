# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

import pytest

from app.modules.site_settings.models import SiteSetting
from tests.modules.site_settings.resources import utils as conf_utils
from tests.utils import module_unavailable

BUNDLE_PATH = 'block'


@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
@pytest.mark.parametrize(
    'keys,user_var',
    (
        (['site.name', 'email_service'], 'admin_user'),
        ({'email_service': 'mailchimp'}, 'admin_user'),
        (
            {
                'recaptchaPublicKey': 'recaptcha-key',
                'flatfileKey': 'flatfile-key',
                'EXCLUDED': ['email_service'],
            },
            'researcher_1',
        ),
        (
            {
                'recaptchaPublicKey': 'recaptcha-key',
                'EXCLUDED': ['email_service', 'flatfileKey'],
            },
            'None',
        ),
    ),
)
def test_bundle_read(flask_app_client, request, admin_user, researcher_1, keys, user_var):
    from app.modules.site_settings.models import SiteSetting

    SiteSetting.set('recaptchaPublicKey', string='recaptcha-key')
    request.addfinalizer(lambda: SiteSetting.forget_key_value('recaptchaPublicKey'))
    SiteSetting.set('flatfileKey', string='flatfile-key')
    request.addfinalizer(lambda: SiteSetting.forget_key_value('flatfileKey'))

    response = conf_utils.read_main_settings(flask_app_client, eval(user_var))

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
    'data,invalid_keys, expected_status_code',
    (
        # Case 1: One valid site setting (succeeds)
        ({'site.name': f'TEST-{str(uuid.uuid4())}'}, [], 200),
        # Case 2: More than one valid site settings (succeeds)
        (
            {
                'email_default_sender_name': 'testing',
                'recaptchaPublicKey': 'recaptcha-public-key',
            },
            [],
            200,
        ),
        # Case 4: Two valid site settings and one invalid key (fails)
        (
            {
                'email_default_sender_name': 'Testing',
                'bad_key': 'abcd',
                'site.name': f'TEST-{str(uuid.uuid4())}',
            },
            ['bad_key'],
            400,
        ),
    ),
)
def test_bundle_modify(
    flask_app_client,
    admin_user,
    db,
    request,
    data,
    invalid_keys,
    expected_status_code,
):

    response = conf_utils.read_main_settings(flask_app_client, admin_user)
    old_values = {}
    for key in data:
        old_value = response.json['response']['configuration'].get(key, {})
        if old_value:
            old_values[key] = old_value['value']
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
        assert response.json['updated']
        assert isinstance(response.json['updated'], list)
        for key, value in data.items():
            assert key in response.json['updated']
            assert SiteSetting.get_value(key) == value
    else:
        for key in invalid_keys:
            if key in response.json['message']:
                break
        else:
            assert (
                False
            ), f'Expected one of {invalid_keys} to be in message "{response.json["message"]}"'
