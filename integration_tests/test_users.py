# -*- coding: utf-8 -*-
import uuid


def test_user_deactivation(session, codex_url, login, logout, admin_email):
    login(session)

    # Create new user
    new_email = f'{uuid.uuid4()}@localhost'
    new_user = {
        'email': new_email,
        'password': 'password',
        'full_name': 'My name',
    }
    response = session.post(
        codex_url('/api/v1/users/'),
        json=new_user,
    )
    assert response.status_code == 200
    assert response.json()['email'] == new_email
    new_user_guid = response.json()['guid']

    # Deactivate user
    response = session.delete(codex_url(f'/api/v1/users/{new_user_guid}'))
    assert response.status_code == 204

    response = session.get(codex_url(f'/api/v1/users/{new_user_guid}'))
    assert '@deactivated' in response.json()['email']
    assert response.json()['full_name'] == 'Inactivated User'
    assert logout(session) == {}

    # Unable to sign up as a new user with the same email address
    response = session.post(
        codex_url('/api/v1/users/'),
        json=new_user,
    )
    assert response.status_code == 200
    assert (
        response.json()['message']
        == 'The email address is already in use in an inactivated user.'
    )

    # Reactivation
    login(session)
    response = session.post(
        codex_url('/api/v1/users/'),
        json=new_user,
    )
    assert response.status_code == 200
    assert response.json()['guid'] == new_user_guid
    assert response.json()['email'] == new_email

    # DELETE user
    response = session.delete(codex_url(f'/api/v1/users/{new_user_guid}'))
    assert response.status_code == 204
