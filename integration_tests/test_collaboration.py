# -*- coding: utf-8 -*-
import uuid


def test_collaboration(session, codex_url, login, admin_email):
    login(session)
    response = session.get(codex_url('/api/v1/users/me'))
    assert response.status_code == 200
    assert response.json()['email'] == admin_email
    my_guid = response.json()['guid']

    # Create a new user
    new_email = f'{uuid.uuid4()}@localhost'
    response = session.post(
        codex_url('/api/v1/users/'),
        json={'email': new_email, 'password': 'password'},
    )
    assert response.status_code == 200
    assert response.json()['email'] == new_email
    new_user_guid = response.json()['guid']

    # Create a collaboration with the new user
    response = session.post(
        codex_url('/api/v1/collaborations/'),
        json={'user_guid': new_user_guid},
    )
    assert response.status_code == 200
    assert set(response.json()['members'].keys()) == {new_user_guid, my_guid}
    collaboration_guid = response.json()['guid']

    # Check collaboration is in /users/me
    response = session.get(codex_url('/api/v1/users/me'))
    assert response.status_code == 200
    assert collaboration_guid in [c['guid'] for c in response.json()['collaborations']]
