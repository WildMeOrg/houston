# -*- coding: utf-8 -*-
import json
import re
from unittest import mock

from app.modules.auth.models import Code, CodeTypes


def test_reset_password(flask_app_client, researcher_1):
    url = '/api/v1/users/reset_password_email'
    with mock.patch('app.extensions.email.mail.send') as send:
        response = flask_app_client.post(url)
        assert response.status_code == 400
        assert (
            response.json['message']
            == 'JSON body needs to be in this format {"email": "user@example.org"}'
        )

        response = flask_app_client.post(
            url,
            content_type='application/json',
            data=json.dumps({'email': researcher_1.email}),
        )
        assert response.status_code == 200
    email = send.call_args[0][0]
    assert email.recipients == [researcher_1.email]
    all_hrefs = re.findall('href="([^"]*)"', email.html) + re.findall(
        'href=([^"> ]+)', email.html
    )
    code = Code.get(researcher_1, CodeTypes.recover, create=False)
    assert f'http://localhost:84/auth/code/{code.accept_code}' in all_hrefs


def test_verify_account(flask_app_client, researcher_1):
    url = '/api/v1/users/verify_account_email'
    with mock.patch('app.extensions.email.mail.send') as send:
        response = flask_app_client.post(url)
        assert response.status_code == 401

        with flask_app_client.login(researcher_1):
            response = flask_app_client.post(url)
            assert response.status_code == 200

    email = send.call_args[0][0]
    assert email.recipients == [researcher_1.email]
    code = Code.get(researcher_1, CodeTypes.email, create=False)
    assert f'action=http://localhost:84/api/v1/auth/code/{code.accept_code}' in email.html
