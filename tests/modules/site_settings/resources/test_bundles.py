# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

import pytest

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
                'NO_ACCESS': ['email_service'],
            },
            'researcher_1',
        ),
        (
            {
                'recaptchaPublicKey': 'recaptcha-key',
                'NO_ACCESS': ['email_service', 'flatfileKey'],
            },
            'None',
        ),
    ),
)
def test_bundle_read(flask_app_client, request, admin_user, researcher_1, keys, user_var):
    from app.modules.site_settings.models import SiteSetting

    SiteSetting.set_key_value('recaptchaPublicKey', 'recaptcha-key')
    request.addfinalizer(lambda: SiteSetting.forget_key_value('recaptchaPublicKey'))
    SiteSetting.set_key_value('flatfileKey', 'flatfile-key')
    request.addfinalizer(lambda: SiteSetting.forget_key_value('flatfileKey'))

    response = conf_utils.read_main_settings(flask_app_client, eval(user_var)).json

    assert isinstance(response, dict)

    if isinstance(keys, dict):
        for key in keys.pop('NO_ACCESS', []):
            assert key in response
            assert not response[key]['canView']

    for key in keys:
        assert key in response
        assert 'value' in response[key]
        assert response[key]['canView']
        if isinstance(keys, dict):
            value = keys[key]
            assert response[key]['value'] == value
        else:
            assert response[key]['value'] is not None


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
        old_value = response.json.get(key, {})
        if old_value:
            old_values[key] = old_value['value']
    request.addfinalizer(
        lambda: conf_utils.modify_main_settings(flask_app_client, admin_user, old_values)
    )
    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        data,
        expected_status_code=expected_status_code,
    )
