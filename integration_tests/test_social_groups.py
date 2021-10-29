# -*- coding: utf-8 -*-
def test_social_groups(session, login, codex_url):
    # Create social group roles
    login(session)
    data = {
        'key': 'social_group_roles',
        'data': {
            'Matriarch': {'multipleInGroup': False},
            'Patriarch': {'multipleInGroup': True},
        },
    }
    response = session.post(codex_url('/api/v1/site-settings/'), json=data)
    assert response.status_code == 200
    assert response.json() == {
        'key': 'social_group_roles',
        'data': {
            'Matriarch': {'multipleInGroup': False},
            'Patriarch': {'multipleInGroup': True},
        },
        'created': response.json()['created'],  # 2021-10-29T20:17:46.585288+00:00
        'string': response.json()['string'],  # '' or None
        'file_upload_guid': None,
        'public': True,
        'updated': response.json()['updated'],
    }

    # Create encounters
    data = {
        'locationId': 'PYTEST-SIGHTING',
        'startTime': '2000-01-01T01:01:01Z',
        'encounters': [
            {'locationId': 'PYTEST-ENCOUNTER-0'},
            {'locationId': 'PYTEST-ENCOUNTER-1'},
            {'locationId': 'PYTEST-ENCOUNTER-2'},
        ],
    }
    response = session.post(codex_url('/api/v1/sightings/'), json=data)
    assert response.status_code == 200
    result = response.json()['result']
    encounter_ids = [e['id'] for e in result['encounters']]
    encounter_versions = [e['version'] for e in result['encounters']]
    assert response.json() == {
        'success': True,
        'result': {
            'id': result['id'],  # 7934b1db-6d5f-405a-9502-88f754fa9179
            'version': result['version'],  # 1635538733340,
            'encounters': [
                {
                    # 06292cf1-1168-43ac-b6a0-40972afb9af3
                    'id': encounter_ids[0],
                    'version': encounter_versions[0],  # 1635538733339
                },
                {
                    'id': encounter_ids[1],
                    'version': encounter_versions[1],
                },
                {
                    'id': encounter_ids[2],
                    'version': encounter_versions[2],
                },
            ],
            'assets': {},
        },
    }

    # Create individuals
    responses = []
    for i in range(3):
        data = {'encounters': [{'id': encounter_ids[i]}]}
        responses.append(session.post(codex_url('/api/v1/individuals/'), json=data))
        assert responses[-1].status_code == 200
    result = responses[0].json()['result']
    individual_ids = [r.json()['result']['id'] for r in responses]
    assert responses[0].json() == {
        'success': True,
        'result': {
            'id': individual_ids[0],  # 7934b1db-6d5f-405a-9502-88f754fa9179
            'version': None,
            'encounters': [
                {
                    'id': encounter_ids[0],
                    'version': encounter_versions[0],
                }
            ],
        },
    }

    # Create social group
    data = {
        'name': 'Family',
        'members': {
            individual_ids[0]: {'roles': ['Matriarch']},
            individual_ids[1]: {},
            individual_ids[2]: {'roles': ['Patriarch']},
        },
    }
    response = session.post(codex_url('/api/v1/social-groups/'), json=data)
    assert response.status_code == 200
    social_group = response.json()
    social_group_id = social_group['guid']
    assert response.json() == {
        'created': social_group['created'],
        'updated': social_group['updated'],
        'name': 'Family',
        'members': {
            individual_ids[0]: {'roles': ['Matriarch']},
            individual_ids[1]: {'roles': None},
            individual_ids[2]: {'roles': ['Patriarch']},
        },
        'guid': social_group_id,
    }

    # GET social group
    response = session.get(codex_url(f'/api/v1/social-groups/{social_group_id}'))
    assert response.status_code == 200
    assert response.json() == social_group

    response = session.get(codex_url('/api/v1/social-groups/'))
    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert {'name': 'Family', 'guid': social_group_id} in response.json()

    # PATCH social group: remove member
    data = [
        {
            'op': 'remove',
            'path': '/member',
            'value': individual_ids[1],
        },
    ]
    response = session.patch(
        codex_url(f'/api/v1/social-groups/{social_group_id}'),
        json=data,
    )
    assert response.status_code == 200
    assert response.json() == {
        'created': social_group['created'],
        'updated': social_group['updated'],
        'name': 'Family',
        'members': {
            individual_ids[0]: {'roles': ['Matriarch']},
            individual_ids[2]: {'roles': ['Patriarch']},
        },
        'guid': social_group_id,
    }

    # PATCH social group: add member
    data = [
        {
            'op': 'add',
            'path': '/member',
            'value': {
                'guid': individual_ids[1],
                'roles': None,
            },
        },
    ]
    response = session.patch(
        codex_url(f'/api/v1/social-groups/{social_group_id}'),
        json=data,
    )
    assert response.status_code == 200
    assert response.json() == {
        'created': social_group['created'],
        'updated': social_group['updated'],
        'name': 'Family',
        'members': {
            individual_ids[0]: {'roles': ['Matriarch']},
            individual_ids[1]: {'roles': None},
            individual_ids[2]: {'roles': ['Patriarch']},
        },
        'guid': social_group_id,
    }

    # PATCH social group: replace members
    data = [
        {
            'op': 'replace',
            'path': '/members',
            'value': {
                individual_ids[0]: {'roles': ['Matriarch']},
                individual_ids[1]: {'roles': None},
            },
        },
    ]
    response = session.patch(
        codex_url(f'/api/v1/social-groups/{social_group_id}'),
        json=data,
    )
    assert response.status_code == 200
    assert response.json() == {
        'created': social_group['created'],
        'updated': social_group['updated'],
        'name': 'Family',
        'members': {
            individual_ids[0]: {'roles': ['Matriarch']},
            individual_ids[1]: {'roles': None},
        },
        'guid': social_group_id,
    }
