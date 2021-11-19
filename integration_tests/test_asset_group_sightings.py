# -*- coding: utf-8 -*-
import datetime
import random

from . import utils


def test_asset_group_sightings(session, login, codex_url, test_root):
    login(session)

    response = session.get(codex_url('/api/v1/users/me'))
    my_guid = response.json()['guid']
    my_name = response.json()['full_name']

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
            'description': 'This is a test asset group, please ignore',
            'sightings': [
                {
                    'assetReferences': ['zebra.jpg'],
                    'bearing': bearing,
                    'customFields': {occ_test_cfd: 'OCC_TEST_CFD'},
                    'decimalLatitude': -39.063228,
                    'decimalLongitude': 21.832598,
                    'distance': distance,
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
    assets = response.json()['assets']
    annots_0 = assets[0]['annotations']
    encounters = response.json()['encounters']
    encounter_guids = [e['guid'] for e in encounters]
    assert response.status_code == 200
    assert response.json() == {
        'assets': [
            {
                'annotations': [
                    {
                        'asset_guid': assets[0]['guid'],
                        'bounds': {
                            'rect': [178, 72, 604, 534],
                            'theta': 0.0,
                        },
                        # 2021-11-09T11:15:09.910872+00:00
                        'created': annots_0[0]['created'],
                        'encounter_guid': None,
                        'guid': annots_0[0]['guid'],
                        'ia_class': 'zebra_plains',
                        'keywords': [],
                        'viewpoint': 'unknown',
                        'updated': annots_0[0]['updated'],
                    },
                ],
                # 2021-11-09T11:15:08.923895+00:00
                'created': assets[0]['created'],
                'dimensions': {'width': 1000, 'height': 664},
                'filename': 'zebra.jpg',
                'guid': assets[0]['guid'],
                'src': f'/api/v1/assets/src/{assets[0]["guid"]}',
                'updated': assets[0]['updated'],
            },
        ],
        # missing 'bearing': bearing,
        'comments': 'None',
        'completion': 10,
        'createdEDM': None,
        # 2021-11-12T18:28:32.744114+00:00
        'createdHouston': response.json()['createdHouston'],
        'customFields': {occ_test_cfd: 'OCC_TEST_CFD'},
        'decimalLatitude': -39.063228,
        'decimalLongitude': 21.832598,
        # missing 'distance': distance,
        'encounterCounts': {},
        'encounters': [
            {
                'country': 'TEST',
                # 2021-11-13T16:57:41.937173+00:00
                'createdHouston': encounters[0]['createdHouston'],
                'customFields': {
                    enc_test_cfd: 'CFD_TEST_VALUE',
                },
                'decimalLatitude': 63.142385,
                'decimalLongitude': -21.596914,
                'guid': encounter_guids[0],
                'hasEdit': True,
                'hasView': True,
                'id': encounter_guids[0],
                'individual': {},
                'locationId': 'enc-test',
                'owner': {
                    'full_name': my_name,
                    'guid': my_guid,
                    'profile_fileupload': None,
                },
                'sex': 'male',
                'submitter': None,
                'taxonomy': {'id': tx_id},
                'time': encounter_timestamp,
                # 2021-11-13T16:57:41.937187+00:00
                'updatedHouston': response.json()['updatedHouston'],
                'version': None,
            },
        ],
        'featuredAssetGuid': None,
        'guid': ags_guids[0],
        'hasEdit': True,
        'hasView': True,
        'id': ags_guids[0],
        'locationId': 'PYTEST',
        'stage': 'curation',
        'startTime': '2000-01-01T01:01:01Z',
        # 2021-11-12T18:28:32.744135+00:00
        'updatedHouston': response.json()['updatedHouston'],
        'verbatimLocality': '',
        'version': None,
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
                'annotations': [
                    {
                        'asset_guid': assets[0]['guid'],
                        'bounds': {
                            'rect': [178, 72, 604, 534],
                            'theta': 0.0,
                        },
                        # 2021-11-09T11:15:09.910872+00:00
                        'created': annots_0[0]['created'],
                        'encounter_guid': None,
                        'guid': annots_0[0]['guid'],
                        'ia_class': 'zebra_plains',
                        'keywords': [],
                        'viewpoint': 'unknown',
                        'updated': annots_0[0]['updated'],
                    },
                ],
                # 2021-11-09T11:15:08.923895+00:00
                'created': assets[0]['created'],
                'dimensions': {'width': 1000, 'height': 664},
                'filename': 'zebra.jpg',
                'guid': assets[0]['guid'],
                'src': f'/api/v1/assets/src/{assets[0]["guid"]}',
                'updated': assets[0]['updated'],
            },
        ],
        'comments': 'None',
        'completion': 10,
        'createdEDM': None,
        # 2021-11-12T18:28:32.744114+00:00
        'createdHouston': response.json()['createdHouston'],
        'customFields': {occ_test_cfd: 'OCC_TEST_CFD'},
        'decimalLatitude': 52.152029,
        'decimalLongitude': 2.318116,
        'encounterCounts': {},
        'encounters': [
            {
                'country': 'TEST',
                # 2021-11-13T16:57:41.937173+00:00
                'createdHouston': encounters[0]['createdHouston'],
                'customFields': {
                    enc_test_cfd: 'CFD_TEST_VALUE',
                },
                'decimalLatitude': 63.142385,
                'decimalLongitude': -21.596914,
                'guid': encounter_guids[0],
                'hasEdit': True,
                'hasView': True,
                'id': encounter_guids[0],
                'individual': {},
                'locationId': 'enc-test',
                'owner': {
                    'full_name': my_name,
                    'guid': my_guid,
                    'profile_fileupload': None,
                },
                'sex': 'male',
                'submitter': None,
                'taxonomy': {'id': tx_id},
                'time': encounter_timestamp,
                # 2021-11-13T16:57:41.937187+00:00
                'updatedHouston': response.json()['updatedHouston'],
                'version': None,
            },
        ],
        'featuredAssetGuid': None,
        'guid': ags_guids[0],
        'hasEdit': True,
        'hasView': True,
        'id': ags_guids[0],
        'locationId': 'PYTEST',
        'stage': 'curation',
        'startTime': '2000-01-01T01:01:01Z',
        # 2021-11-12T18:28:32.744135+00:00
        'updatedHouston': response.json()['updatedHouston'],
        'verbatimLocality': '',
        'version': None,
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
