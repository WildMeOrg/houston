# -*- coding: utf-8 -*-
import json
from unittest import mock

import pytest
import requests.exceptions
import werkzeug.exceptions

from app.modules.auth.utils import recaptcha_required


def test_recaptcha_required_skipped(flask_app):
    # recaptchaPublicKey not set up
    result = mock.Mock()

    with flask_app.test_request_context():

        @recaptcha_required
        def f():
            return result

        assert f() == result


def test_recaptcha_required_bypass(flask_app, request):
    from app.modules.site_settings.models import SiteSetting

    SiteSetting.set_key_value('recaptchaPublicKey', 'public')
    request.addfinalizer(lambda: SiteSetting.forget_key_value('recaptchaPublicKey'))
    SiteSetting.set_key_value('recaptchaSecretKey', 's-e-c-r-e-t')
    request.addfinalizer(lambda: SiteSetting.forget_key_value('recaptchaSecretKey'))
    result = mock.Mock()

    with flask_app.test_request_context():
        with mock.patch('app.modules.auth.utils.request') as flask_request:
            flask_request.data = json.dumps({'token': 'XXX'})

            @recaptcha_required
            def f():
                return result

            assert f() == result


def test_recaptcha_required_verify_token(flask_app, request):
    from app.modules.site_settings.models import SiteSetting

    SiteSetting.set_key_value('recaptchaPublicKey', 'public')
    request.addfinalizer(lambda: SiteSetting.forget_key_value('recaptchaPublicKey'))
    SiteSetting.set_key_value('recaptchaSecretKey', 's-e-c-r-e-t')
    request.addfinalizer(lambda: SiteSetting.forget_key_value('recaptchaSecretKey'))

    # Patch log so it doesn't do anything
    patch_log = mock.patch('app.modules.auth.utils.log')
    patch_log.start()
    request.addfinalizer(patch_log.stop)

    # Patch time.sleep so it doesn't sleep
    patch_sleep = mock.patch('time.sleep')
    patch_sleep.start()
    request.addfinalizer(patch_sleep.stop)

    result = mock.Mock()

    # Patch requests.post
    patch_requests_post = mock.patch('requests.post')
    post = patch_requests_post.start()
    request.addfinalizer(patch_requests_post.stop)

    with flask_app.test_request_context():
        # Patch flask.request
        patch_request = mock.patch('app.modules.auth.utils.request')
        flask_request = patch_request.start()
        request.addfinalizer(patch_request.stop)

        flask_request.data = json.dumps({'token': 'qwerty123456'})

        @recaptcha_required
        def f():
            return result

        # Case 1: score > 0.5 (human)
        response = mock.Mock()
        response.json.return_value = {'success': True, 'score': 0.9}
        post.return_value = response

        assert f() == result

        # Case 2: score < 0.5 (bot)
        response.json.return_value = {'success': True, 'score': 0.1}

        with pytest.raises(werkzeug.exceptions.BadRequest) as exc:
            f()
        assert str(exc.value) == '400 Bad Request: Recaptcha bot score failed'

        # Case 3: success is False
        response.json.return_value = {
            'success': False,
            'error-codes': ['invalid-input-response'],
        }

        with pytest.raises(werkzeug.exceptions.BadRequest) as exc:
            f()
        assert (
            str(exc.value)
            == "400 Bad Request: Recaptcha response failure: {'success': False, 'error-codes': ['invalid-input-response']}"
        )

        # Case 4: ConnectionError or RequestException
        post.reset_mock()

        def mock_post(*args, **kwargs):
            if post.call_count < 3:
                raise requests.exceptions.ConnectionError
            elif post.call_count < 11:
                raise requests.exceptions.RequestException
            return response

        post.side_effect = mock_post

        with pytest.raises(werkzeug.exceptions.BadRequest) as exc:
            f()

        assert str(exc.value) == '400 Bad Request: Recaptcha response failure: {}'
        assert post.call_count == 10

        post.reset_mock()

        def mock_post(*args, **kwargs):
            if post.call_count < 3:
                raise requests.exceptions.ConnectionError
            elif post.call_count < 4:
                raise requests.exceptions.RequestException
            return response

        response.json.return_value = {'success': True, 'score': 0.9}

        post.side_effect = mock_post

        assert f() == result

        assert post.call_count == 4
