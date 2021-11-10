# -*- coding: utf-8 -*-
import datetime
import random

from . import utils


def test_asset_group_sightings(session, login, codex_url, test_root):
    login(session)

    response = session.get(codex_url('/api/v1/users/me'))
    my_guid = response.json()['guid']

    # Add an example species and custom fields in edm
    response = utils.add_site_species(
        session,
        codex_url,
        {'commonNames': ['Example'], 'scientificName': 'Exempli gratia'},
    )
    tx_id = response.json()['response']['value'][-1]['id']
    occ_test_cfd = utils.create_custom_field(
        session, codex_url, 'Occurrence', 'occ_test_cfd'
    )
    enc_test_cfd = utils.create_custom_field(
        session, codex_url, 'Encounter', 'enc_test_cfd'
    )

    # Create asset group sighting
    transaction_id = utils.upload_to_tus(
        session,
        codex_url,
        [test_root / 'zebra.jpg'],
    )
    # 2021-11-09T11:40:53.802Z
    encounter_timestamp = datetime.datetime.now().isoformat()[:-3] + 'Z'
    bearing = random.uniform(0, 180)
    distance = random.uniform(1, 100)
    response = session.post(
        codex_url('/api/v1/asset_groups/'),
        json={
            'bearing': bearing,
            'customFields': {occ_test_cfd: 'OCC_TEST_CFD'},
            'description': 'This is a test asset group, please ignore',
            'decimalLatitude': -39.063228,
            'decimalLongitude': 21.832598,
            'distance': distance,
            'sightings': [
                {
                    'assetReferences': ['zebra.jpg'],
                    'encounters': [
                        {
                            'country': 'TEST',
                            'customFields': {
                                enc_test_cfd: 'CFD_TEST_VALUE',
                            },
                            'decimalLatitude': 63.142385,
                            'decimalLongitude': -21.596914,
                            'locationId': 'enc-test',
                            'sex': 'male',
                            'taxonomy': {'id': tx_id},
                            'time': encounter_timestamp,
                        },
                    ],
                    'locationId': 'PYTEST',
                    'startTime': '2000-01-01T01:01:01Z',
                },
            ],
            'speciesDetectionModel': ['african_terrestrial'],
            'taxonomies': [{'id': tx_id}],
            'transactionId': transaction_id,
            'uploadType': 'form',
        },
    )
    assert response.status_code == 200
    assets = response.json()['assets']
    ags_guids = [a['guid'] for a in response.json()['asset_group_sightings']]
    asset_group_guid = response.json()['guid']
    assert response.json() == {
        'assets': [
            {
                'guid': assets[0]['guid'],
                'filename': assets[0]['filename'],
                'src': f'/api/v1/assets/src/{assets[0]["guid"]}',
            },
        ],
        'asset_group_sightings': [
            {
                'guid': ags_guids[0],
            },
        ],
        'commit': response.json()['commit'],
        # 2021-11-08T07:37:31.076636+00:00
        'created': response.json()['created'],
        'description': 'This is a test asset group, please ignore',
        'guid': asset_group_guid,
        'major_type': 'filesystem',
        'owner_guid': my_guid,
        'updated': response.json()['updated'],
    }
    assert set(a['filename'] for a in assets) == {'zebra.jpg'}

    # Wait for detection
    ags_url = codex_url(f'/api/v1/asset_groups/sighting/{ags_guids[0]}')
    utils.wait_for(
        session.get, ags_url, lambda response: response.json()['stage'] == 'curation'
    )

    # GET asset group sighting as sighting
    response = session.get(
        codex_url(f'/api/v1/asset_groups/sighting/as_sighting/{ags_guids[0]}')
    )
    encounter_guids = [e['guid'] for e in response.json()['encounters']]
    assert response.status_code == 200
    assert response.json() == {
        'assets': [
            {
                'guid': assets[0]['guid'],
                'filename': assets[0]['filename'],
                'src': f'/api/v1/assets/src/{assets[0]["guid"]}',
            },
        ],
        'completion': 10,
        'decimalLatitude': None,
        'decimalLongitude': None,
        'encounterCounts': {},
        'encounters': [
            {
                'country': 'TEST',
                'customFields': {
                    enc_test_cfd: 'CFD_TEST_VALUE',
                },
                'decimalLatitude': 63.142385,
                'decimalLongitude': -21.596914,
                'guid': encounter_guids[0],
                'locationId': 'enc-test',
                'sex': 'male',
                'taxonomy': {'id': tx_id},
                'time': encounter_timestamp,
            },
        ],
        'featured_asset_guid': None,
        'guid': ags_guids[0],
        'id': None,
        'locationId': 'PYTEST',
        'stage': 'curation',
        'startTime': '2000-01-01T01:01:01Z',
        'verbatimLocality': '',
    }

    # PATCH asset group sighting as sighting
    response = session.patch(
        codex_url(f'/api/v1/asset_groups/sighting/as_sighting/{ags_guids[0]}'),
        json=[
            {
                'op': 'add',
                'path': '/decimalLatitude',
                'value': 52.152029,
            },
            {
                'op': 'add',
                'path': '/decimalLongitude',
                'value': 2.318116,
            },
        ],
    )
    assert response.status_code == 200
    assert response.json() == {
        'assets': [
            {
                'filename': 'zebra.jpg',
                'src': f'/api/v1/assets/src/{assets[0]["guid"]}',
                'guid': assets[0]['guid'],
            },
        ],
        'completion': 10,
        'decimalLatitude': 52.152029,
        'decimalLongitude': 2.318116,
        'encounters': [
            {
                'country': 'TEST',
                'customFields': {
                    enc_test_cfd: 'CFD_TEST_VALUE',
                },
                'decimalLatitude': 63.142385,
                'decimalLongitude': -21.596914,
                'guid': encounter_guids[0],
                'locationId': 'enc-test',
                'sex': 'male',
                'taxonomy': {'id': tx_id},
                'time': encounter_timestamp,
            },
        ],
        'encounterCounts': {},
        'featured_asset_guid': None,
        'guid': ags_guids[0],
        'id': None,
        'locationId': 'PYTEST',
        'stage': 'curation',
        'startTime': '2000-01-01T01:01:01Z',
        'verbatimLocality': '',
    }

    # Commit asset group sighting (becomes sighting)
    response = session.post(
        codex_url(f'/api/v1/asset_groups/sighting/{ags_guids[0]}/commit')
    )
    assert response.status_code == 200
    sighting_guid = response.json()['guid']
    assert response.json() == {'guid': sighting_guid}

    # GET sighting
    response = session.get(codex_url(f'/api/v1/sightings/{sighting_guid}'))
    assert response.status_code == 200

    # DELETE asset group
    response = session.delete(codex_url(f'/api/v1/asset_groups/{asset_group_guid}'))
    assert response.status_code == 204

    # DELETE sighting
    response = session.delete(codex_url(f'/api/v1/sightings/{sighting_guid}'))
    assert response.status_code == 204
