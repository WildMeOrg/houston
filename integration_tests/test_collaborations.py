# -*- coding: utf-8 -*-
import uuid

from .utils import create_new_user


def test_collaboration(session, codex_url, login, logout, admin_email):
    login(session)
    response = session.get(codex_url('/api/v1/users/me'))
    assert response.status_code == 200
    assert response.json()['email'] == admin_email
    my_guid = response.json()['guid']

    # Create a new user
    new_email = f'{uuid.uuid4()}@localhost'
    new_user_guid = create_new_user(session, codex_url, new_email)

    # Create another new user
    new_email_2 = f'{uuid.uuid4()}@localhost'
    new_user_guid_2 = create_new_user(session, codex_url, new_email_2)

    # Create a collaboration with the new user
    response = session.post(
        codex_url('/api/v1/collaborations/'),
        json={'user_guid': new_user_guid},
    )
    assert response.status_code == 200
    assert set(response.json()['members'].keys()) == {new_user_guid, my_guid}
    assert response.json()['members'][my_guid]['viewState'] == 'approved'
    assert response.json()['members'][my_guid]['editState'] == 'not_initiated'
    assert response.json()['members'][new_user_guid]['viewState'] == 'pending'
    assert response.json()['members'][new_user_guid]['editState'] == 'not_initiated'
    collaboration_guid = response.json()['guid']

    # Check collaboration is in /users/me
    response = session.get(codex_url('/api/v1/users/me'))
    assert response.status_code == 200
    assert collaboration_guid in [c['guid'] for c in response.json()['collaborations']]

    # Create a collaboration between new users
    response = session.post(
        codex_url('/api/v1/collaborations/'),
        json={'user_guid': new_user_guid, 'second_user_guid': new_user_guid_2},
    )
    assert response.status_code == 200
    assert set(sorted(response.json()['members'].keys())) == set(
        {new_user_guid, new_user_guid_2}
    )
    assert response.json()['members'][new_user_guid]['viewState'] == 'approved'
    assert response.json()['members'][new_user_guid]['editState'] == 'not_initiated'
    assert response.json()['members'][new_user_guid_2]['viewState'] == 'approved'
    assert response.json()['members'][new_user_guid_2]['editState'] == 'not_initiated'
    collaboration_guid_2 = response.json()['guid']

    # Check collaboration is in /users/me
    response = session.get(codex_url('/api/v1/users/me'))
    assert response.status_code == 200
    assert collaboration_guid_2 in [c['guid'] for c in response.json()['collaborations']]
    logout(session)

    # Log in as new user and check collaboration request
    login(session, new_email, password='password')
    response = session.get(codex_url('/api/v1/users/me'))
    assert response.status_code == 200
    assert collaboration_guid in [c['guid'] for c in response.json()['collaborations']]
    response = session.get(codex_url(f'/api/v1/collaborations/{collaboration_guid}'))
    assert response.status_code == 200

    # Invalid view_permission
    response = session.patch(
        codex_url(f'/api/v1/collaborations/{collaboration_guid}'),
        json=[{'op': 'replace', 'path': '/view_permission', 'value': True}],
    )
    assert response.status_code == 409
    assert (
        response.json()['message']
        == 'State "True" not in allowed states: denied, approved, pending, not_initiated, revoked, manager_creator, manager_revoked'
    )

    # Approve collaboration
    response = session.patch(
        codex_url(f'/api/v1/collaborations/{collaboration_guid}'),
        json=[{'op': 'replace', 'path': '/view_permission', 'value': 'approved'}],
    )
    assert response.status_code == 200
    assert response.json()['members'][my_guid]['viewState'] == 'approved'
    assert response.json()['members'][my_guid]['editState'] == 'not_initiated'
    assert response.json()['members'][new_user_guid]['viewState'] == 'approved'
    assert response.json()['members'][new_user_guid]['editState'] == 'not_initiated'

    # Create edit request
    response = session.post(
        codex_url(f'/api/v1/collaborations/edit_request/{collaboration_guid}'),
    )
    assert response.status_code == 200
    assert response.json()['members'][my_guid]['viewState'] == 'approved'
    assert response.json()['members'][my_guid]['editState'] == 'pending'
    assert response.json()['members'][new_user_guid]['viewState'] == 'approved'
    assert response.json()['members'][new_user_guid]['editState'] == 'approved'
    logout(session)

    # Invalid edit_permission
    login(session)
    response = session.patch(
        codex_url(f'/api/v1/collaborations/{collaboration_guid}'),
        json=[{'op': 'replace', 'path': '/edit_permission', 'value': False}],
    )
    assert response.status_code == 409
    assert (
        response.json()['message']
        == 'State "False" not in allowed states: denied, approved, pending, not_initiated, revoked, manager_creator, manager_revoked'
    )

    # Reject collaboration for edit
    response = session.patch(
        codex_url(f'/api/v1/collaborations/{collaboration_guid}'),
        json=[{'op': 'replace', 'path': '/edit_permission', 'value': 'denied'}],
    )
    assert response.status_code == 200
    assert response.json()['members'][my_guid]['viewState'] == 'approved'
    assert response.json()['members'][my_guid]['editState'] == 'denied'
    assert response.json()['members'][new_user_guid]['viewState'] == 'approved'
    assert response.json()['members'][new_user_guid]['editState'] == 'approved'

    # DELETE new users
    response = session.delete(codex_url(f'/api/v1/users/{new_user_guid}'))
    assert response.status_code == 204
    response = session.delete(codex_url(f'/api/v1/users/{new_user_guid_2}'))
    assert response.status_code == 204
