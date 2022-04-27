# -*- coding: utf-8 -*-
from . import utils


# Not a generic util as there are fixed number of things
def create_sighting(session, codex_url, test_root, filename, group_data=None):
    transaction_id = utils.upload_to_tus(session, codex_url, [test_root / filename])
    if not group_data:
        group_data = {
            'description': 'This is a test asset_group, please ignore',
            'uploadType': 'form',
            'speciesDetectionModel': ['african_terrestrial'],
            'transactionId': transaction_id,
            'sightings': [
                {
                    'time': '2000-01-01T01:01:01+00:00',
                    'timeSpecificity': 'time',
                    'locationId': 'Tiddleywink',
                    'encounters': [{}],
                    'assetReferences': [filename],
                    'idConfigs': [
                        {
                            'algorithms': ['hotspotter_nosv'],
                        }
                    ],
                },
            ],
        }
    else:
        group_data['transactionId'] = transaction_id

    asset_group_guid, asset_group_sighting_guids, asset_guids = utils.create_asset_group(
        session, codex_url, group_data
    )
    assert len(asset_group_sighting_guids) == 1
    ags_guid = asset_group_sighting_guids[0]
    assert len(asset_guids) == 1

    ags_url = codex_url(f'/api/v1/asset_groups/sighting/{ags_guid}')
    response = utils.wait_for(
        session.get, ags_url, lambda response: response.json()['stage'] == 'curation'
    )
    response_json = response.json()

    assert len(response_json['assets']) == 1
    assert len(response_json['assets'][0]['annotations']) == 1
    annot_guid = response_json['assets'][0]['annotations'][0]['guid']

    encounter_guids = [enc['guid'] for enc in response_json['config']['encounters']]

    assert len(encounter_guids) == 1
    encounter_guid = encounter_guids[0]

    # We got an annotation back, need to add it to the encounter in the sighting
    patch_response = session.patch(
        codex_url(f'/api/v1/asset_groups/sighting/{ags_guid}/encounter/{encounter_guid}'),
        json=[{'op': 'add', 'path': '/annotations', 'value': annot_guid}],
    )
    assert patch_response.status_code == 200
    # Commit it
    commit_response = session.post(
        codex_url(f'/api/v1/asset_groups/sighting/{ags_guid}/commit')
    )
    assert commit_response.status_code == 200

    return {
        'asset_group': asset_group_guid,
        'ags': ags_guid,
        'asset': asset_guids[0],
        'sighting': commit_response.json()['guid'],
        'annotation': annot_guid,
        'encounter': encounter_guid,
    }


def test_create_asset_group_identification(session, codex_url, test_root, login):
    login(session)
    zebra_guids = create_sighting(session, codex_url, test_root, 'zebra-flopped.jpg')

    # Check jobs data for first AGS
    zebra_ags = session.get(
        codex_url(f"/api/v1/asset_groups/sighting/{zebra_guids['ags']}")
    )
    assert len(zebra_ags.json()['jobs']) == 1
    job_data = zebra_ags.json()['jobs'][0]
    assert not job_data['active']

    # the first one does not go for identification, so make it processed so that the next one can
    patch_response = session.post(
        codex_url(f"/api/v1/sightings/{zebra_guids['sighting']}/reviewed"),
        json=[],
    )
    assert patch_response.status_code == 200
    zebra2_guids = create_sighting(session, codex_url, test_root, 'zebra2.jpg')

    # Sighting should be being identified
    response = session.get(codex_url(f"/api/v1/sightings/{zebra2_guids['sighting']}"))

    assert response.status_code == 200

    assert 'stage' in response.json().keys()
    assert response.json()['stage'] == 'identification'
    zebra2_sighting_guid = zebra2_guids['sighting']

    sight_url = codex_url(f'/api/v1/sightings/{zebra2_sighting_guid}')
    response = utils.wait_for(
        session.get, sight_url, lambda response: response.json()['stage'] == 'un_reviewed'
    )

    id_result = session.get(
        codex_url(f"/api/v1/sightings/{zebra2_guids['sighting']}/id_result")
    )
    assert id_result.status_code == 200
    id_resp = id_result.json()
    assert 'query_annotations' in id_resp.keys()
    assert len(id_resp['query_annotations']) == 1
    query_annot = id_resp['query_annotations'][0]
    assert query_annot['status'] == 'pending'
    assert query_annot['guid'] in id_resp['annotation_data'].keys()

    # Check that we got job data back
    zebra_sighting = session.get(
        codex_url(f"/api/v1/sightings/{zebra2_guids['sighting']}")
    )
    id_job_data = zebra_sighting.json()['jobs'][0]
    assert not id_job_data['active']


def test_identification_international(session, codex_url, test_root, login):
    login(session)
    zebra_guids = create_sighting(session, codex_url, test_root, 'zebra-flopped.jpg')

    # the first one does not go for identification, so make it processed so that the next one can
    patch_response = session.post(
        codex_url(f"/api/v1/sightings/{zebra_guids['sighting']}/reviewed"),
        json=[],
    )
    assert patch_response.status_code == 200
    description = 'International names Þröstur Sélène cédric characters &%$* ¼ ©,® ™ m².'
    location = 'Montréal'

    # Going to get nasty now and put international characters in here
    filename = 'zebra-named-Sigurður.jpg'
    group_data = {
        'description': description,
        'uploadType': 'form',
        'speciesDetectionModel': ['african_terrestrial'],
        'sightings': [
            {
                'time': '2000-01-01T01:01:01+00:00',
                'timeSpecificity': 'time',
                'locationId': 'Tiddleywink',
                'verbatimLocation': location,
                'encounters': [
                    {
                        'verbatimLocation': location,
                    }
                ],
                'assetReferences': [filename],
                'idConfigs': [
                    {
                        'algorithms': ['hotspotter_nosv'],
                    }
                ],
            },
        ],
    }
    zebra2_guids = create_sighting(session, codex_url, test_root, filename, group_data)
    # Sighting should be being identified
    response = session.get(codex_url(f"/api/v1/sightings/{zebra2_guids['sighting']}"))

    assert response.status_code == 200

    assert 'stage' in response.json().keys()
    assert response.json()['stage'] == 'identification'
    zebra2_sighting_guid = zebra2_guids['sighting']

    sight_url = codex_url(f'/api/v1/sightings/{zebra2_sighting_guid}')
    response = utils.wait_for(
        session.get, sight_url, lambda response: response.json()['stage'] == 'un_reviewed'
    )

    # Check internationalisation data
    zebra2_group = session.get(
        codex_url(f"/api/v1/asset_groups/{zebra2_guids['asset_group']}")
    ).json()
    assert zebra2_group['description'] == description

    zebra2_ags = session.get(
        codex_url(f"/api/v1/asset_groups/sighting/{zebra2_guids['ags']}")
    ).json()
    assert zebra2_ags['config']['verbatimLocation'] == location
    assert zebra2_ags['config']['encounters'][0]['verbatimLocation'] == location

    id_result = session.get(
        codex_url(f"/api/v1/sightings/{zebra2_guids['sighting']}/id_result")
    )
    assert id_result.status_code == 200
    id_resp = id_result.json()
    assert 'query_annotations' in id_resp.keys()
    assert len(id_resp['query_annotations']) == 1
    query_annot = id_resp['query_annotations'][0]
    assert query_annot['status'] == 'complete'
    assert query_annot['guid'] in id_resp['annotation_data'].keys()

    # Check that we got job data back
    zebra_sighting = session.get(
        codex_url(f"/api/v1/sightings/{zebra2_guids['sighting']}")
    )
    id_job_data = zebra_sighting.json()['jobs'][0]
    assert not id_job_data['active']
