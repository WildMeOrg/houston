# -*- coding: utf-8 -*-
import uuid


def test_notification_preferences(session, login, logout, codex_url):
    # Create new user
    login(session)
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
    user_guid = response.json()['guid']
    logout(session)

    login(session, email=new_email)
    response = session.get(codex_url('/api/v1/users/me'))
    assert response.status_code == 200
    assert response.json()['notification_preferences'] == {
        'all': {'restAPI': True, 'email': False},
        'raw': {'restAPI': True, 'email': True},
        'collaboration_request': {'restAPI': True, 'email': False},
        'collaboration_edit_request': {'restAPI': True, 'email': False},
        'individual_merge_request': {'restAPI': True, 'email': False},
    }
    user_guid = response.json()['guid']

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
        'all': {
            'restAPI': True,
            'email': False,
        },
        'raw': {
            'restAPI': True,
            'email': True,
        },
        'collaboration_request': {
            'restAPI': True,
            'email': False,
        },
        'collaboration_edit_request': {
            'restAPI': True,
            'email': False,
        },
        'individual_merge_request': {
            'restAPI': False,
            'email': False,
        },
    }
