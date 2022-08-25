# -*- coding: utf-8 -*-
import uuid

from .utils import create_new_user


def test_notification_preferences(session, login, logout, codex_url):
    # Create new user
    login(session)
    new_email = f'{uuid.uuid4()}@localhost'
    user_guid = create_new_user(session, codex_url, new_email, full_name='My name')
    logout(session)

    # GET user
    login(session, email=new_email, password='password')
    response = session.get(codex_url('/api/v1/users/me'))
    assert response.status_code == 200
    assert response.json()['notification_preferences'] == {
        'all': {'restAPI': True, 'email': False},
        'collaboration_request': {'restAPI': True, 'email': False},
        'collaboration_approved': {'email': False, 'restAPI': True},
        'collaboration_denied': {'email': False, 'restAPI': True},
        'collaboration_revoke': {'email': False, 'restAPI': True},
        'collaboration_edit_request': {'restAPI': True, 'email': False},
        'collaboration_edit_approved': {'email': False, 'restAPI': True},
        'collaboration_edit_denied': {'email': False, 'restAPI': True},
        'collaboration_edit_revoke': {'email': False, 'restAPI': True},
        'collaboration_manager_create': {'email': False, 'restAPI': True},
        'collaboration_manager_revoke': {'email': False, 'restAPI': True},
        'collaboration_manager_denied': {'email': False, 'restAPI': True},
        'collaboration_manager_edit_approved': {'email': False, 'restAPI': True},
        'collaboration_manager_edit_denied': {'email': False, 'restAPI': True},
        'collaboration_manager_edit_revoke': {'email': False, 'restAPI': True},
        'individual_merge_request': {'restAPI': True, 'email': False},
        'individual_merge_blocked': {'restAPI': True, 'email': False},
        'individual_merge_complete': {'restAPI': True, 'email': False},
    }
    user_guid = response.json()['guid']

    # PATCH user notification preferences
    response = session.patch(
        codex_url(f'/api/v1/users/{user_guid}'),
        json=[
            {
                'op': 'replace',
                'path': '/notification_preferences',
                'value': {
                    'collaboration_request': {'restAPI': True, 'email': True},
                },
            },
            {
                'op': 'replace',
                'path': '/notification_preferences',
                'value': {
                    'individual_merge_request': {'restAPI': False, 'email': False},
                },
            },
        ],
    )
    assert response.status_code == 200
    assert response.json()['notification_preferences'] == {
        'all': {'restAPI': True, 'email': False},
        'collaboration_request': {'restAPI': True, 'email': True},
        'collaboration_approved': {'email': False, 'restAPI': True},
        'collaboration_denied': {'email': False, 'restAPI': True},
        'collaboration_revoke': {'email': False, 'restAPI': True},
        'collaboration_edit_request': {'restAPI': True, 'email': False},
        'collaboration_edit_approved': {'email': False, 'restAPI': True},
        'collaboration_edit_revoke': {'email': False, 'restAPI': True},
        'collaboration_edit_denied': {'email': False, 'restAPI': True},
        'collaboration_manager_create': {'email': False, 'restAPI': True},
        'collaboration_manager_revoke': {'email': False, 'restAPI': True},
        'collaboration_manager_denied': {'email': False, 'restAPI': True},
        'collaboration_manager_edit_approved': {'email': False, 'restAPI': True},
        'collaboration_manager_edit_denied': {'email': False, 'restAPI': True},
        'collaboration_manager_edit_revoke': {'email': False, 'restAPI': True},
        'individual_merge_request': {'restAPI': False, 'email': False},
        'individual_merge_blocked': {'restAPI': True, 'email': False},
        'individual_merge_complete': {'restAPI': True, 'email': False},
    }

    # DELETE user
    response = session.delete(codex_url(f'/api/v1/users/{user_guid}'))
    assert response.status_code == 204
