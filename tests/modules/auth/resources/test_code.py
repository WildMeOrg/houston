# -*- coding: utf-8 -*-
import datetime

from app.modules.auth.models import Code, CodeTypes
from app.modules.users.models import User


def test_reset_password(flask_app_client, researcher_1, request):
    # Create a recover code
    recover = Code.get(researcher_1, CodeTypes.recover)
    request.addfinalizer(recover.delete)

    # Use the recover code without sending a password
    response = flask_app_client.post(f'/api/v1/auth/code/{recover.accept_code}.json')
    assert response.status_code == 400
    assert response.json['message'] == 'Empty password not allowed'

    # Use the recover code to reset password
    response = flask_app_client.post(
        f'/api/v1/auth/code/{recover.accept_code}.json',
        content_type='application/json',
        data='{"password": "new-password"}',
    )
    assert response.status_code == 200
    assert response.json['message'] == 'Password successfully set.'
    assert User.find(email=researcher_1.email, password='new-password') == researcher_1

    # Use the recover code again
    response = flask_app_client.post(
        f'/api/v1/auth/code/{recover.accept_code}.json',
        content_type='application/json',
        data='{"password": "new-password"}',
    )
    assert response.status_code == 400
    assert response.json['message'] == 'Code already used'

    # Create a recover code that is expired
    expired = Code.get(researcher_1, CodeTypes.recover)
    expired.expires -= datetime.timedelta(days=3650)

    # Use an expired recover code
    response = flask_app_client.post(
        f'/api/v1/auth/code/{expired.accept_code}.json',
        content_type='application/json',
        data='{"password": "new-password"}',
    )
    assert response.status_code == 400
    assert response.json['message'] == 'Code has expired'

    # Use a code that does not exist
    response = flask_app_client.post(
        '/api/v1/auth/code/1234',
        content_type='application/json',
        data='{"password": "new-password"}',
    )
    assert response.status_code == 404
    assert response.json['message'] == "Code '1234' not found"


def test_verify_account(flask_app_client, researcher_1, request):
    # Create a verify code
    verify = Code.get(researcher_1, CodeTypes.email)
    request.addfinalizer(verify.delete)

    # Use the verify code
    response = flask_app_client.post(f'/api/v1/auth/code/{verify.accept_code}')
    assert response.status_code == 302
    assert (
        response.headers['Location']
        == 'http://localhost/email_verified?message=Email+successfully+verified.&status=200'
    )
    assert researcher_1.is_email_confirmed is True

    # Use the verify code again
    response = flask_app_client.post(f'/api/v1/auth/code/{verify.accept_code}')
    assert response.status_code == 302
    assert (
        response.headers['Location']
        == 'http://localhost/email_verified?message=Code+already+used&status=400'
    )

    # Create a verify code that is expired
    expired = Code.get(researcher_1, CodeTypes.email)
    expired.expires -= datetime.timedelta(days=3650)

    # Use an expired recover code
    response = flask_app_client.post(f'/api/v1/auth/code/{expired.accept_code}')
    assert response.status_code == 302
    assert (
        response.headers['Location']
        == 'http://localhost/email_verified?message=Code+has+expired&status=400'
    )

    # Use a code that does not exist
    response = flask_app_client.post('/api/v1/auth/code/1234')
    assert response.status_code == 404
    assert response.json['message'] == "Code '1234' not found"
