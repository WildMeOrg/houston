# -*- coding: utf-8 -*-
import datetime

from . import utils


def test_sightings(session, login, codex_url, test_root, admin_name):
    login(session)

    response = session.get(codex_url('/api/v1/users/me'))
    my_name = response.json()['full_name']
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

    # Create sighting by committing asset group sighting
    transaction_id = utils.upload_to_tus(
        session,
        codex_url,
        [test_root / 'zebra.jpg'],
    )
    # 2021-11-09T11:40:53.802Z
    encounter_timestamp = datetime.datetime.now().isoformat()[:-3] + 'Z'
    response = session.post(
        codex_url('/api/v1/asset_groups/'),
        json={
            'description': 'This is a test asset group, please ignore',
            'sightings': [
                {
                    'assetReferences': ['zebra.jpg'],
                    'customFields': {occ_test_cfd: 'OCC_TEST_CFD'},
                    'decimalLatitude': -39.063228,
                    'decimalLongitude': 21.832598,
                    'encounters': [
                        {
                            'customFields': {
                                enc_test_cfd: 'CFD_TEST_VALUE',
                            },
                            'decimalLatitude': 63.142385,
                            'decimalLongitude': -21.596914,
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
    asset_group_guid = response.json()['guid']
    ags_guids = [s['guid'] for s in response.json()['asset_group_sightings']]

    # Wait for detection
    ags_url = codex_url(f'/api/v1/asset_groups/sighting/{ags_guids[0]}')
    utils.wait_for(
        session.get, ags_url, lambda response: response.json()['stage'] == 'curation'
    )

    # Commit asset group sighting which returns a sighting
    response = session.post(
        codex_url(f'/api/v1/asset_groups/sighting/{ags_guids[0]}/commit')
    )
    assert response.status_code == 200
    sighting_id = response.json()['guid']
    assert response.json() == {
        'guid': sighting_id,
        'created': response.json()['created'],
        'encounters': response.json()['encounters'],
        'hasEdit': True,
        'hasView': True,
        'updated': response.json()['updated'],
    }

    # GET sighting
    response = session.get(codex_url(f'/api/v1/sightings/{sighting_id}'))
    assert response.status_code == 200
    sighting_version = response.json()['version']
    assets = response.json()['assets']
    annots_0 = response.json()['assets'][0]['annotations']
    encounters = response.json()['encounters']
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
        'createdEDM': response.json()['createdEDM'],  # 2021-11-09 11:15:24
        # 2021-11-09T11:15:24.316645+00:00
        'createdHouston': response.json()['createdHouston'],
        'customFields': {occ_test_cfd: 'OCC_TEST_CFD'},
        'decimalLatitude': -39.063228,
        'decimalLongitude': 21.832598,
        'encounters': [
            {
                # 2021-11-09T11:15:24.343018+00:00
                'createdHouston': encounters[0]['createdHouston'],
                'customFields': {
                    enc_test_cfd: 'CFD_TEST_VALUE',
                },
                'decimalLatitude': 63.142385,
                'decimalLongitude': -21.596914,
                'guid': encounters[0]['guid'],
                'hasEdit': True,
                'hasView': True,
                'id': encounters[0]['guid'],
                'individual': {},
                'owner': {
                    'full_name': my_name,
                    'guid': my_guid,
                    'profile_fileupload': None,
                },
                'sex': 'male',
                'submitter': None,
                'taxonomy': {
                    'commonNames': ['Example'],
                    'scientificName': 'Exempli gratia',
                    'id': tx_id,
                },
                'time': encounter_timestamp,
                'updatedHouston': encounters[0]['updatedHouston'],
                'version': encounters[0]['version'],  # 1636456524261
            },
        ],
        'encounterCounts': {
            'sex': {'male': 1},
            'individuals': 0,
        },
        'featuredAssetGuid': assets[0]['guid'],
        'guid': sighting_id,
        'hasEdit': True,
        'hasView': True,
        'id': sighting_id,
        'locationId': 'PYTEST',
        'startTime': '2000-01-01T01:01:01Z',
        'stage': 'un_reviewed',
        # FIXME missing taxonomies: [{'id': tx_id}],
        'updatedHouston': response.json()['updatedHouston'],
        'version': response.json()['version'],  # 1636456524261
        'creator': {
            'full_name': 'Test admin',
            'guid': my_guid,
            'profile_fileupload': None,
        },
    }

    # PATCH sighting
    response = session.patch(
        codex_url(f'/api/v1/sightings/{sighting_id}'),
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
    assert response.json()['version'] > sighting_version
    sighting_version = response.json()['version']
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
                        'created': annots_0[0]['created'],
                        'encounter_guid': None,
                        'guid': annots_0[0]['guid'],
                        'ia_class': 'zebra_plains',
                        'keywords': [],
                        'updated': annots_0[0]['updated'],
                        'viewpoint': 'unknown',
                    },
                ],
                'created': assets[0]['created'],
                'dimensions': {'width': 1000, 'height': 664},
                'filename': 'zebra.jpg',
                'guid': assets[0]['guid'],
                'src': f'/api/v1/assets/src/{assets[0]["guid"]}',
                'updated': assets[0]['updated'],
            },
        ],
        'comments': 'None',
        'createdEDM': response.json()['createdEDM'],  # 2021-11-16 09:45:26
        # 2021-11-16T09:45:26.717326+00:00
        'createdHouston': response.json()['createdHouston'],
        'customFields': {occ_test_cfd: 'OCC_TEST_CFD'},
        'decimalLatitude': 52.152029,
        'decimalLongitude': 2.318116,
        'encounters': [
            {
                'createdHouston': encounters[0]['createdHouston'],
                'customFields': {
                    enc_test_cfd: 'CFD_TEST_VALUE',
                },
                'decimalLatitude': 63.142385,
                'decimalLongitude': -21.596914,
                'guid': encounters[0]['guid'],
                'hasEdit': True,
                'hasView': True,
                'id': encounters[0]['guid'],
                'individual': {},
                'owner': {
                    'full_name': my_name,
                    'guid': my_guid,
                    'profile_fileupload': None,
                },
                'sex': 'male',
                'submitter': None,
                'taxonomy': {
                    'commonNames': ['Example'],
                    'scientificName': 'Exempli gratia',
                    'id': tx_id,
                },
                'time': encounter_timestamp,
                'updatedHouston': encounters[0]['updatedHouston'],
                'version': encounters[0]['version'],
            },
        ],
        'encounterCounts': {
            'sex': {'male': 1},
            'individuals': 0,
        },
        'featuredAssetGuid': assets[0]['guid'],
        'guid': sighting_id,
        'hasEdit': True,
        'hasView': True,
        'id': sighting_id,
        'locationId': 'PYTEST',
        'startTime': '2000-01-01T01:01:01Z',
        'stage': 'un_reviewed',
        # 2021-11-16T09:45:26.717432+00:00
        'updatedHouston': response.json()['updatedHouston'],
        'version': sighting_version,
        'creator': {
            'full_name': 'Test admin',
            'guid': my_guid,
            'profile_fileupload': None,
        },
    }

    # DELETE asset group
    response = session.delete(codex_url(f'/api/v1/asset_groups/{asset_group_guid}'))
    assert response.status_code == 204
