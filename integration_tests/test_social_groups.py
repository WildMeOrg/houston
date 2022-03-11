# -*- coding: utf-8 -*-
from . import utils


# Not a generic util as there has to be exactly one asset group sighting, no assets, one sighting, and three
# encounters,
def create_sighting(session, codex_url):
    group_data = {
        'description': 'This is a test asset_group, please ignore',
        'uploadType': 'bulk',
        'speciesDetectionModel': ['None'],
        'sightings': [
            {
                'time': '2000-01-01T01:01:01+00:00',
                'timeSpecificity': 'time',
                'locationId': 'PYTEST-SIGHTING',
                'encounters': [{}, {}, {}],
            },
        ],
    }
    asset_group_guid, asset_group_sighting_guids, asset_guids = utils.create_asset_group(
        session, codex_url, group_data
    )
    assert len(asset_group_sighting_guids) == 1
    ags_guid = asset_group_sighting_guids[0]

    # Should not need a wait, should be just a get
    ags_url = codex_url(f'/api/v1/asset_groups/sighting/{ags_guid}')
    ags_json = session.get(ags_url).json()
    assert len(ags_json['assets']) == 0
    assert ags_json['stage'] == 'processed'
    assert 'sighting_guid' in ags_json.keys()

    sighting_guid = ags_json['sighting_guid']
    sight_url = codex_url(f'/api/v1/sightings/{sighting_guid}')
    sight_json = session.get(sight_url).json()
    assert sight_json['stage'] == 'un_reviewed'
    assert len(sight_json['encounters']) == 3

    encounter_guids = [enc['guid'] for enc in sight_json['encounters']]
    assert len(encounter_guids) == 3

    return {
        'asset_group': asset_group_guid,
        'ags': ags_guid,
        'sighting': sighting_guid,
        'encounters': encounter_guids,
    }


def test_social_groups(session, login, codex_url):
    # Create social group roles
    login(session)
    data = [
        {'label': 'Matriarch', 'multipleInGroup': False},
        {'label': 'Patriarch', 'multipleInGroup': True},
    ]
    response = session.post(
        codex_url('/api/v1/site-settings/main/social_group_roles'), json={'_value': data}
    )
    assert response.status_code == 200
    assert response.json() == {
        'key': 'social_group_roles',
        'success': True,
    }

    uuids = create_sighting(session, codex_url)
    asset_group_id = uuids['asset_group']
    encounter_ids = uuids['encounters']

    # Create individuals
    responses = []
    for i in range(3):
        data = {'encounters': [{'id': encounter_ids[i]}]}
        responses.append(session.post(codex_url('/api/v1/individuals/'), json=data))
        assert responses[-1].status_code == 200

    individual_ids = [r.json()['result']['id'] for r in responses]
    assert responses[0].json() == {
        'success': True,
        'result': {
            'id': individual_ids[0],  # 7934b1db-6d5f-405a-9502-88f754fa9179
            'version': None,
            'encounters': [
                {
                    'id': encounter_ids[0],
                    'version': responses[0].json()['result']['encounters'][0]['version'],
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
        'indexed': social_group['indexed'],
        'elasticsearchable': social_group['elasticsearchable'],
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
    assert response.json() == [
        {
            'name': 'Family',
            'guid': social_group_id,
            'elasticsearchable': social_group['elasticsearchable'],
            'indexed': social_group['indexed'],
        }
    ]

    # PATCH social group: remove member
    data = [
        {
            'op': 'remove',
            'path': '/members',
            'value': [individual_ids[1]],
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
        'indexed': social_group['indexed'],
        'elasticsearchable': social_group['elasticsearchable'],
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
            'path': '/members',
            'value': {
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
        'indexed': social_group['indexed'],
        'elasticsearchable': social_group['elasticsearchable'],
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
        'indexed': social_group['indexed'],
        'elasticsearchable': social_group['elasticsearchable'],
        'name': 'Family',
        'members': {
            individual_ids[0]: {'roles': ['Matriarch']},
            individual_ids[1]: {'roles': None},
        },
        'guid': social_group_id,
    }

    # DELETE social group
    response = session.delete(codex_url(f'/api/v1/social-groups/{social_group_id}'))
    assert response.status_code == 204

    # DELETE individuals
    for individual_id in individual_ids:
        response = session.delete(codex_url(f'/api/v1/individuals/{individual_id}'))
        assert response.status_code == 204

    # DELETE sighting
    response = session.delete(codex_url(f'/api/v1/asset_groups/{asset_group_id}'))
    assert response.status_code == 204
