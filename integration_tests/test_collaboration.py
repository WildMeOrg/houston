# -*- coding: utf-8 -*-
import uuid

from .utils import create_new_user


def test_collaboration(session, codex_url, login, admin_email):
    login(session)
    response = session.get(codex_url('/api/v1/users/me'))
    assert response.status_code == 200
    assert response.json()['email'] == admin_email
    my_guid = response.json()['guid']

    # Create a new user
    new_email = f'{uuid.uuid4()}@localhost'
    new_user_guid = create_new_user(session, codex_url, new_email)

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
