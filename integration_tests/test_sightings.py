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
    enc_custom_fields = {enc_test_cfd: 'CFD_TEST_VALUE'}

    occ_custom_fields = {occ_test_cfd: 'OCC_TEST_CFD'}
    # Create sighting by committing asset group sighting
    transaction_id = utils.upload_to_tus(
        session,
        codex_url,
        [test_root / 'zebra.jpg'],
    )
    # 2021-11-09T11:40:53.802+00:00
    encounter_timestamp = datetime.datetime.now().isoformat() + '+00:00'
    response = session.post(
        codex_url('/api/v1/asset_groups/'),
        json={
            'token': 'XXX',
            'description': 'This is a test asset group, please ignore',
            'sightings': [
                {
                    'assetReferences': ['zebra.jpg'],
                    'customFields': occ_custom_fields,
                    'decimalLatitude': -39.063228,
                    'decimalLongitude': 21.832598,
                    'encounters': [
                        {
                            'customFields': enc_custom_fields,
                            'decimalLatitude': 63.142385,
                            'decimalLongitude': -21.596914,
                            'sex': 'male',
                            'taxonomy': tx_id,
                            'time': encounter_timestamp,
                            'timeSpecificity': 'time',
                        },
                    ],
                    'locationId': 'PYTEST',
                    'time': '2000-01-01T01:01:01+00:00',
                    'timeSpecificity': 'time',
                },
            ],
            'speciesDetectionModel': ['african_terrestrial'],
            'taxonomies': [tx_id],
            'transactionId': transaction_id,
            'uploadType': 'form',
        },
    )
    response = utils.wait_for_progress(session, codex_url, response, 'preparation')

    assert response.status_code == 200, response.json()
    asset_group_guid = response.json()['guid']
    ags_guids = [s['guid'] for s in response.json()['asset_group_sightings']]

    # Wait for detection
    ags_url = codex_url(f'/api/v1/asset_groups/sighting/{ags_guids[0]}')
    utils.wait_for(
        session.get, ags_url, lambda response: response.json()['stage'] == 'curation'
    )

    utils.set_id_config_for_ags(session, codex_url, ags_guids[0])

    # Commit asset group sighting which returns a sighting
    response = session.post(
        codex_url(f'/api/v1/asset_groups/sighting/{ags_guids[0]}/commit')
    )
    assert response.status_code == 200, response.json()
    sighting_id = response.json()['guid']
    # No need to validate the contents, that's tested as part of the asset group sighting tests

    # but do need to wait for it to be un-reviewed
    sight_url = codex_url(f'/api/v1/sightings/{sighting_id}')
    response = utils.wait_for(
        session.get, sight_url, lambda response: response.json()['stage'] == 'un_reviewed'
    )

    # GET sighting
    response = session.get(codex_url(f'/api/v1/sightings/{sighting_id}'))
    assert response.status_code == 200, response.json()
    sighting_version = response.json()['version']
    assets = response.json()['assets']
    annots_0 = response.json()['assets'][0]['annotations']
    encounters = response.json()['encounters']
    assert response.json() == {
        'assets': [
            {
                'git_store': {
                    'elasticsearchable': assets[0]['git_store']['elasticsearchable'],
                    'indexed': assets[0]['git_store']['indexed'],
                    'guid': assets[0]['git_store']['guid'],
                    'commit': assets[0]['git_store']['commit'],
                    'description': assets[0]['git_store']['description'],
                    'major_type': assets[0]['git_store']['major_type'],
                },
                'annotations': [
                    {
                        'guid': annots_0[0]['guid'],
                        'bounds': annots_0[0]['bounds'],
                        'created': annots_0[0]['created'],
                        'updated': annots_0[0]['updated'],
                        'keywords': [],
                        'asset_guid': assets[0]['guid'],
                        'asset_src': annots_0[0]['asset_src'],
                        'encounter_guid': None,
                        'ia_class': 'zebra',
                        'viewpoint': 'right',
                        'elasticsearchable': annots_0[0]['elasticsearchable'],
                        'indexed': annots_0[0]['indexed'],
                    },
                ],
                # 2021-11-09T11:15:08.923895+00:00
                'classifications': None,
                'created': assets[0]['created'],
                'indexed': assets[0]['indexed'],
                'elasticsearchable': assets[0]['elasticsearchable'],
                'dimensions': {'width': 1000, 'height': 664},
                'filename': 'zebra.jpg',
                'guid': assets[0]['guid'],
                'src': f'/api/v1/assets/src/{assets[0]["guid"]}',
                'tags': [],
                'updated': assets[0]['updated'],
            },
        ],
        'comments': 'None',
        'createdEDM': response.json()['createdEDM'],  # 2021-11-09 11:15:24
        # 2021-11-09T11:15:24.316645+00:00
        'createdHouston': response.json()['createdHouston'],
        'customFields': occ_custom_fields,
        'decimalLatitude': -39.063228,
        'decimalLongitude': 21.832598,
        'speciesDetectionModel': ['african_terrestrial'],
        'idConfigs': [{'algorithms': ['hotspotter_nosv']}],
        'encounters': [
            {
                # 2021-11-09T11:15:24.343018+00:00
                'createdHouston': encounters[0]['createdHouston'],
                'customFields': enc_custom_fields,
                'decimalLatitude': 63.142385,
                'decimalLongitude': -21.596914,
                'guid': encounters[0]['guid'],
                'hasEdit': True,
                'hasView': True,
                'individual': None,
                'owner': {
                    'full_name': my_name,
                    'guid': my_guid,
                    'profile_fileupload': None,
                },
                'annotations': [],
                'sex': 'male',
                'submitter': None,
                'taxonomy': tx_id,
                'time': encounter_timestamp,
                'timeSpecificity': 'time',
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
        'jobs': [],
        'hasEdit': True,
        'hasView': True,
        'locationId': 'PYTEST',
        'time': '2000-01-01T01:01:01+00:00',
        'timeSpecificity': 'time',
        'stage': 'un_reviewed',
        # FIXME missing taxonomies: [{'id': tx_id}],
        'updatedHouston': response.json()['updatedHouston'],
        'version': response.json()['version'],  # 1636456524261
        'creator': {
            'full_name': my_name,
            'guid': my_guid,
            'profile_fileupload': None,
        },
        'created': response.json()['created'],
        'updated': response.json()['updated'],
        'indexed': response.json()['indexed'],
        'submissionTime': response.json()['submissionTime'],
        'detection_start_time': response.json()['detection_start_time'],
        'elasticsearchable': response.json()['elasticsearchable'],
        'curation_start_time': response.json()['curation_start_time'],
        'identification_start_time': None,
        'unreviewed_start_time': response.json()['unreviewed_start_time'],
        'progress_identification': response.json()['progress_identification'],
        'review_time': None,
        'pipeline_status': response.json()['pipeline_status'],
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
    assets = response.json()['assets']
    annots_0 = response.json()['assets'][0]['annotations']
    sighting_version = response.json()['version']
    assert response.json() == {
        'assets': [
            {
                'git_store': {
                    'guid': assets[0]['git_store']['guid'],
                    'commit': assets[0]['git_store']['commit'],
                    'description': assets[0]['git_store']['description'],
                    'major_type': assets[0]['git_store']['major_type'],
                    'elasticsearchable': assets[0]['git_store']['elasticsearchable'],
                    'indexed': assets[0]['git_store']['indexed'],
                },
                'annotations': [
                    {
                        'asset_guid': assets[0]['guid'],
                        'asset_src': annots_0[0]['asset_src'],
                        'encounter_guid': None,
                        'guid': annots_0[0]['guid'],
                        'elasticsearchable': annots_0[0]['elasticsearchable'],
                        'ia_class': 'zebra',
                        'viewpoint': 'right',
                        'bounds': annots_0[0]['bounds'],
                        'created': annots_0[0]['created'],
                        'updated': annots_0[0]['updated'],
                        'indexed': annots_0[0]['indexed'],
                        'keywords': [],
                    },
                ],
                'classifications': None,
                'created': assets[0]['created'],
                'dimensions': {'width': 1000, 'height': 664},
                'filename': 'zebra.jpg',
                'guid': assets[0]['guid'],
                'elasticsearchable': assets[0]['elasticsearchable'],
                'src': f'/api/v1/assets/src/{assets[0]["guid"]}',
                'tags': [],
                'updated': assets[0]['updated'],
                'indexed': assets[0]['indexed'],
            },
        ],
        'comments': 'None',
        'createdEDM': response.json()['createdEDM'],  # 2021-11-16 09:45:26
        # 2021-11-16T09:45:26.717326+00:00
        'createdHouston': response.json()['createdHouston'],
        'customFields': occ_custom_fields,
        'decimalLatitude': 52.152029,
        'decimalLongitude': 2.318116,
        'encounters': [
            {
                'createdHouston': encounters[0]['createdHouston'],
                'customFields': enc_custom_fields,
                'decimalLatitude': 63.142385,
                'decimalLongitude': -21.596914,
                'guid': encounters[0]['guid'],
                'hasEdit': True,
                'hasView': True,
                'individual': None,
                'owner': {
                    'full_name': my_name,
                    'guid': my_guid,
                    'profile_fileupload': None,
                },
                'sex': 'male',
                'annotations': [],
                'submitter': None,
                'taxonomy': tx_id,
                'time': encounter_timestamp,
                'timeSpecificity': 'time',
                'updatedHouston': encounters[0]['updatedHouston'],
                'version': encounters[0]['version'],
            },
        ],
        'encounterCounts': {
            'sex': {'male': 1},
            'individuals': 0,
        },
        'elasticsearchable': response.json()['elasticsearchable'],
        'featuredAssetGuid': assets[0]['guid'],
        'guid': sighting_id,
        'jobs': [],
        'hasEdit': True,
        'hasView': True,
        'locationId': 'PYTEST',
        'time': '2000-01-01T01:01:01+00:00',
        'timeSpecificity': 'time',
        'stage': 'un_reviewed',
        'speciesDetectionModel': ['african_terrestrial'],
        'idConfigs': [{'algorithms': ['hotspotter_nosv']}],
        # 2021-11-16T09:45:26.717432+00:00
        'updatedHouston': response.json()['updatedHouston'],
        'version': sighting_version,
        'creator': {
            'full_name': admin_name,
            'guid': my_guid,
            'profile_fileupload': None,
        },
        'created': response.json()['created'],
        'updated': response.json()['updated'],
        'indexed': response.json()['indexed'],
        'submissionTime': response.json()['submissionTime'],
        'detection_start_time': response.json()['detection_start_time'],
        'curation_start_time': response.json()['curation_start_time'],
        'identification_start_time': None,
        'unreviewed_start_time': response.json()['unreviewed_start_time'],
        'progress_identification': response.json()['progress_identification'],
        'review_time': None,
    }

    # DELETE asset group
    response = session.delete(codex_url(f'/api/v1/asset_groups/{asset_group_guid}'))
    assert response.status_code == 204
