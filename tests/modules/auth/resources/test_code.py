# -*- coding: utf-8 -*-
import datetime

from app.modules.auth.models import Code, CodeTypes
from app.modules.users.models import User


def test_reset_password(flask_app_client, researcher_1, request):
    # Create a recover code
    recover = Code.get(researcher_1, CodeTypes.recover)
    request.addfinalizer(recover.delete)

    # Use the recover code without sending a password
    response = flask_app_client.post(f'/api/v1/auth/code/{recover.accept_code}')
    assert response.status_code == 400
    assert response.json['message'] == 'Empty password not allowed'

    # Use the recover code to reset password
    response = flask_app_client.post(
        f'/api/v1/auth/code/{recover.accept_code}',
        content_type='application/json',
        data='{"password": "new-password"}',
    )
    assert response.status_code == 200
    assert User.find(email=researcher_1.email, password='new-password') == researcher_1

    # Use the recover code again
    response = flask_app_client.post(
        f'/api/v1/auth/code/{recover.accept_code}',
        content_type='application/json',
        data='{"password": "new-password"}',
    )
    assert response.status_code == 400
    assert response.json['message'] == f'Code {repr(recover.accept_code)} already used'

    # Create a recover code that is expired
    expired = Code.get(researcher_1, CodeTypes.recover)
    expired.expires -= datetime.timedelta(days=3650)

    # Use an expired recover code
    response = flask_app_client.post(
        f'/api/v1/auth/code/{expired.accept_code}',
        content_type='application/json',
        data='{"password": "new-password"}',
    )
    assert response.status_code == 400
    assert response.json['message'] == f'Code {repr(expired.accept_code)} is expired'

    # Use a code that does not exist
    response = flask_app_client.post(
        '/api/v1/auth/code/1234',
        content_type='application/json',
        data='{"password": "new-password"}',
    )
    assert response.status_code == 400
    assert response.json['message'] == "Code '1234' not found"
