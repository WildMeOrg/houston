# -*- coding: utf-8 -*-
import time

from . import utils


# Not a generic util as there has to be exactly one asset group sighting, no assets, one sighting, and three
# encounters,
def create_sighting(session, codex_url):
    test_regions = utils.ensure_default_test_regions(session, codex_url)
    region_id1 = test_regions[0]['id']
    group_data = {
        'token': 'XXX',
        'description': 'This is a test asset_group, please ignore',
        'uploadType': 'bulk',
        'speciesDetectionModel': ['None'],
        'sightings': [
            {
                'time': '2000-01-01T01:01:01+00:00',
                'timeSpecificity': 'time',
                'locationId': region_id1,
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
    trial = 0
    while True:
        ags_url = codex_url(f'/api/v1/asset_groups/sighting/{ags_guid}')
        ags_json = session.get(ags_url).json()

        try:
            assert len(ags_json['assets']) == 0
            assert ags_json['stage'] == 'processed'
            assert 'sighting_guid' in ags_json.keys()
            break
        except AssertionError:
            pass

        if trial > 60:
            raise RuntimeError()

        trial += 1
        time.sleep(1)

    sighting_guid = ags_json['sighting_guid']
    sight_url = codex_url(f'/api/v1/sightings/{sighting_guid}')
    # but do need to wait for it to be un-reviewed
    utils.wait_for(
        session.get, sight_url, lambda response: response.json()['stage'] == 'un_reviewed'
    )
    sight_json = session.get(sight_url).json()
    assert sight_json['stage'] in ['identification', 'un_reviewed']
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
    return  # integ tests broken
    # Create social group roles
    login(session)
    import uuid

    matriarch_guid = str(uuid.uuid4())
    patriarch_guid = str(uuid.uuid4())
    data = [
        {'guid': matriarch_guid, 'label': 'Matriarch', 'multipleInGroup': False},
        {'guid': patriarch_guid, 'label': 'Patriarch', 'multipleInGroup': True},
    ]
    response = session.post(
        codex_url('/api/v1/site-settings/data/social_group_roles'), json={'value': data}
    )
    assert response.status_code == 200
    assert response.json() == {
        'key': 'social_group_roles',
        'public': True,
        'value': [
            {'guid': matriarch_guid, 'label': 'Matriarch', 'multipleInGroup': False},
            {'guid': patriarch_guid, 'label': 'Patriarch', 'multipleInGroup': True},
        ],
    }

    uuids = create_sighting(session, codex_url)
    asset_group_id = uuids['asset_group']
    encounter_ids = uuids['encounters']

    # Create individuals
    response = utils.add_site_species(
        session,
        codex_url,
        {'commonNames': ['Example'], 'scientificName': 'Exempli gratia'},
    )
    tx_id = response[-1]['id']
    responses = []
    for i in range(3):
        data = {'encounters': [{'id': encounter_ids[i]}], 'taxonomy': tx_id}
        responses.append(session.post(codex_url('/api/v1/individuals/'), json=data))
        assert responses[-1].status_code == 200

    individual_ids = [r.json()['guid'] for r in responses]

    assert responses[0].json().keys() >= {'guid', 'encounters', 'social_groups'}

    # Create social group
    data = {
        'name': 'Family',
        'members': {
            individual_ids[0]: {'role_guids': [matriarch_guid]},
            individual_ids[1]: {},
            individual_ids[2]: {'role_guids': [patriarch_guid]},
        },
    }
    response = session.post(codex_url('/api/v1/social-groups/'), json=data)
    assert response.status_code == 200
    social_group = response.json()
    social_group_id = social_group['guid']
    assert response.json() == {
        'created': social_group['created'],
        'updated': response.json()['updated'],
        'indexed': response.json()['indexed'],
        'elasticsearchable': response.json()['elasticsearchable'],
        'name': 'Family',
        'members': {
            individual_ids[0]: {'role_guids': [matriarch_guid]},
            individual_ids[1]: {'role_guids': None},
            individual_ids[2]: {'role_guids': [patriarch_guid]},
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
            'created': social_group['created'],
            'updated': response.json()[0]['updated'],
            'guid': social_group_id,
            'elasticsearchable': response.json()[0]['elasticsearchable'],
            'indexed': response.json()[0]['indexed'],
            'num_members': 3,
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
        'updated': response.json()['updated'],
        'indexed': response.json()['indexed'],
        'elasticsearchable': response.json()['elasticsearchable'],
        'name': 'Family',
        'members': {
            individual_ids[0]: {'role_guids': [matriarch_guid]},
            individual_ids[2]: {'role_guids': [patriarch_guid]},
        },
        'guid': social_group_id,
    }

    # PATCH social group: add member
    data = [
        {
            'op': 'add',
            'path': '/members',
            'value': {
                individual_ids[1]: {'role_guids': None},
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
        'updated': response.json()['updated'],
        'indexed': response.json()['indexed'],
        'elasticsearchable': response.json()['elasticsearchable'],
        'name': 'Family',
        'members': {
            individual_ids[0]: {'role_guids': [matriarch_guid]},
            individual_ids[1]: {'role_guids': None},
            individual_ids[2]: {'role_guids': [patriarch_guid]},
        },
        'guid': social_group_id,
    }

    # PATCH social group: replace members
    data = [
        {
            'op': 'replace',
            'path': '/members',
            'value': {
                individual_ids[0]: {'role_guids': [matriarch_guid]},
                individual_ids[1]: {'role_guids': None},
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
        'updated': response.json()['updated'],
        'indexed': response.json()['indexed'],
        'elasticsearchable': response.json()['elasticsearchable'],
        'name': 'Family',
        'members': {
            individual_ids[0]: {'role_guids': [matriarch_guid]},
            individual_ids[1]: {'role_guids': None},
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
