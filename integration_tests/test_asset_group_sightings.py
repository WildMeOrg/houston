# -*- coding: utf-8 -*-
import datetime

from . import utils

# conforms with app.modules.names.models.DEFAULT_NAME_CONTEXT
DEFAULT_NAME_CONTEXT = 'firstName'


def test_asset_group_sightings(session, login, codex_url, test_root):
    login(session)

    response = session.get(codex_url('/api/v1/users/me'))
    my_guid = response.json()['guid']
    my_name = response.json()['full_name']

    creator_data = {
        'full_name': my_name,
        'guid': my_guid,
        'profile_fileupload': None,
    }
    # Add an example species and custom fields in edm
    response = utils.add_site_species(
        session,
        codex_url,
        {'commonNames': ['Example'], 'scientificName': 'Exempli gratia'},
    )
    tx_id = response.json()['response']['value'][-1]['id']
    sighting_test_cfd = utils.create_custom_field(
        session, codex_url, 'Occurrence', 'occ_test_cfd'
    )
    enc_test_cfd = utils.create_custom_field(
        session, codex_url, 'Encounter', 'enc_test_cfd'
    )
    enc_custom_fields = {enc_test_cfd: 'CFD_TEST_VALUE'}
    sighting_custom_fields = {sighting_test_cfd: 'OCC_TEST_CFD'}
    sighting_filename = 'zebra.jpg'

    # Create asset group sighting
    transaction_id = utils.upload_to_tus(
        session,
        codex_url,
        [test_root / sighting_filename],
    )
    # 2021-11-09T11:40:53.802+00:00
    encounter_timestamp = datetime.datetime.now().isoformat() + '+00:00'
    response = session.post(
        codex_url('/api/v1/asset_groups/'),
        json={
            'description': 'This is a test asset group, please ignore',
            'sightings': [
                {
                    'assetReferences': [sighting_filename],
                    'customFields': sighting_custom_fields,
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
    assert response.status_code == 200
    assert len(response.json()['assets']) == 1
    asset = response.json()['assets'][0]
    assert len(response.json()['asset_group_sightings']) == 1
    ags = response.json()['asset_group_sightings'][0]
    ags_guid = ags['guid']
    assert len(ags['assets']) == 1
    ags_asset = ags['assets'][0]
    ags_encounter = ags['config']['encounters'][0]
    asset_group_guid = response.json()['guid']
    assert response.json() == {
        'assets': [
            {
                'elasticsearchable': asset['elasticsearchable'],
                'guid': asset['guid'],
                'indexed': asset['indexed'],
                'filename': sighting_filename,
                'src': f'/api/v1/assets/src/{asset["guid"]}',
            },
        ],
        'asset_group_sightings': [
            {
                'asset_group_guid': asset_group_guid,
                'assets': [
                    {
                        'annotations': [],
                        'created': ags_asset['created'],
                        'dimensions': {'height': 664, 'width': 1000},
                        'elasticsearchable': ags_asset['elasticsearchable'],
                        'filename': sighting_filename,
                        'guid': asset['guid'],
                        'indexed': ags_asset['indexed'],
                        'src': f"/api/v1/assets/src/{asset['guid']}",
                        'updated': ags_asset['updated'],
                    },
                ],
                'completion': 0,
                'config': {
                    'assetReferences': [sighting_filename],
                    'customFields': sighting_custom_fields,
                    'decimalLatitude': -39.063228,
                    'decimalLongitude': 21.832598,
                    'encounters': [
                        {
                            'customFields': enc_custom_fields,
                            'decimalLatitude': 63.142385,
                            'decimalLongitude': -21.596914,
                            'guid': ags_encounter['guid'],
                            'sex': 'male',
                            'taxonomy': ags_encounter['taxonomy'],
                            'time': ags_encounter['time'],
                            'timeSpecificity': 'time',
                        }
                    ],
                    'locationId': 'PYTEST',
                    'time': '2000-01-01T01:01:01+00:00',
                    'timeSpecificity': 'time',
                },
                'creator': creator_data,
                'curation_start_time': ags['curation_start_time'],
                'detection_start_time': ags['detection_start_time'],
                'elasticsearchable': ags['elasticsearchable'],
                'guid': ags_guid,
                'indexed': ags['indexed'],
                'jobs': ags['jobs'],
                'sighting_guid': None,
                'stage': 'detection',
            },
        ],
        'commit': response.json()['commit'],
        # 2021-11-08T07:37:31.076636+00:00
        'created': response.json()['created'],
        'description': 'This is a test asset group, please ignore',
        'elasticsearchable': response.json()['elasticsearchable'],
        'guid': asset_group_guid,
        'indexed': response.json()['indexed'],
        'major_type': 'filesystem',
        'owner_guid': my_guid,
        'updated': response.json()['updated'],
    }

    # Wait for detection
    ags_url = codex_url(f'/api/v1/asset_groups/sighting/{ags_guid}')
    utils.wait_for(
        session.get, ags_url, lambda response: response.json()['stage'] == 'curation'
    )

    # GET asset group sighting as sighting
    response = session.get(
        codex_url(f'/api/v1/asset_groups/sighting/as_sighting/{ags_guid}')
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
                        'asset_src': annots_0[0]['asset_src'],
                        'elasticsearchable': annots_0[0]['elasticsearchable'],
                        'encounter_guid': None,
                        'guid': annots_0[0]['guid'],
                        'ia_class': 'zebra',
                        'viewpoint': 'right',
                        'bounds': annots_0[0]['bounds'],
                        'created': annots_0[0]['created'],
                        'updated': annots_0[0]['updated'],
                        'indexed': annots_0[0]['indexed'],
                        'keywords': [],
                    },
                ],
                # 2021-11-09T11:15:08.923895+00:00
                'created': assets[0]['created'],
                'dimensions': {'width': 1000, 'height': 664},
                'filename': 'zebra.jpg',
                'guid': assets[0]['guid'],
                'elasticsearchable': assets[0]['elasticsearchable'],
                'src': f'/api/v1/assets/src/{assets[0]["guid"]}',
                'updated': assets[0]['updated'],
                'indexed': assets[0]['indexed'],
            },
        ],
        'comments': None,
        'completion': 10,
        'createdEDM': None,
        # 2021-11-12T18:28:32.744114+00:00
        'createdHouston': response.json()['createdHouston'],
        'customFields': sighting_custom_fields,
        'decimalLatitude': -39.063228,
        'decimalLongitude': 21.832598,
        'encounterCounts': {},
        'encounters': [
            {
                'annotations': [],
                # 2021-11-13T16:57:41.937173+00:00
                'createdHouston': encounters[0]['createdHouston'],
                'customFields': enc_custom_fields,
                'decimalLatitude': 63.142385,
                'decimalLongitude': -21.596914,
                'guid': encounter_guids[0],
                'hasEdit': True,
                'hasView': True,
                'locationId': None,
                'verbatimLocality': None,
                'individual': {},
                'owner': creator_data,
                'sex': 'male',
                'submitter': None,
                'taxonomy': tx_id,
                'time': encounter_timestamp,
                'timeSpecificity': 'time',
                # 2021-11-13T16:57:41.937187+00:00
                'updatedHouston': response.json()['updatedHouston'],
                'version': None,
            },
        ],
        'featuredAssetGuid': None,
        'guid': ags_guid,
        'hasEdit': True,
        'hasView': True,
        'locationId': 'PYTEST',
        'stage': 'curation',
        'speciesDetectionModel': ['african_terrestrial'],
        'time': '2000-01-01T01:01:01+00:00',
        'timeSpecificity': 'time',
        # 2021-11-12T18:28:32.744135+00:00
        'updatedHouston': response.json()['updatedHouston'],
        'verbatimLocality': '',
        'verbatimEventDate': '',
        'version': None,
        'asset_group_guid': asset_group_guid,
        'sightingGuid': None,
        'creator': creator_data,
        'created': response.json()['created'],
        'updated': response.json()['updated'],
        'detection_start_time': response.json()['detection_start_time'],
        'curation_start_time': response.json()['curation_start_time'],
        'identification_start_time': response.json()['identification_start_time'],
        'unreviewed_start_time': response.json()['unreviewed_start_time'],
        'review_time': None,
    }

    # PATCH asset group sighting as sighting
    response = session.patch(
        codex_url(f'/api/v1/asset_groups/sighting/as_sighting/{ags_guid}'),
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
    # Just check new fields added
    assert set(response.json()) >= set(
        {
            'decimalLatitude': 52.152029,
            'decimalLongitude': 2.318116,
        }
    )

    # PATCH asset group sightings encounter with sex None
    response = session.patch(
        codex_url(
            f'/api/v1/asset_groups/sighting/as_sighting/{ags_guid}/encounter/{encounter_guids[0]}'
        ),
        json=[
            {
                'op': 'replace',
                'path': '/sex',
                'value': None,
            }
        ],
    )
    assert response.status_code == 200

    assert set(response.json()) >= set(
        {
            'customFields': enc_custom_fields,
            'sex': None,
        },
    )

    # Create a manual annotation on one of the assets
    asset_guid = assets[0]['guid']
    annot_create_response = session.post(
        codex_url('/api/v1/annotations/'),
        json={
            'asset_guid': asset_guid,
            'ia_class': 'noddy',
            'viewpoint': 'underneath',
            'bounds': {'rect': [45, 23, 233, 112]},
        },
    )
    assert annot_create_response.status_code == 200
    assert annot_create_response.json()['asset_guid'] == asset_guid

    # Commit asset group sighting (becomes sighting)
    response = session.post(codex_url(f'/api/v1/asset_groups/sighting/{ags_guid}/commit'))
    assert response.status_code == 200
    sighting_guid = response.json()['guid']
    assert response.json() == {
        'guid': sighting_guid,
        'created': response.json()['created'],
        'encounters': response.json()['encounters'],
        'assets': response.json()['assets'],
        'hasEdit': True,
        'hasView': True,
        'stage': response.json()['stage'],
        'updated': response.json()['updated'],
        'comments': 'None',
        'creator': creator_data,
        'customFields': sighting_custom_fields,
        'createdEDM': response.json()['createdEDM'],
        'decimalLatitude': 52.152029,
        'decimalLongitude': 2.318116,
        'encounterCounts': {'individuals': 0, 'sex': {}},
        'locationId': 'PYTEST',
        'version': response.json()['version'],
        'featuredAssetGuid': response.json()['featuredAssetGuid'],
        'time': response.json()['time'],
        'timeSpecificity': response.json()['timeSpecificity'],
        'createdHouston': response.json()['createdHouston'],
        'updatedHouston': response.json()['updatedHouston'],
        'curation_start_time': response.json()['curation_start_time'],
        'detection_start_time': response.json()['detection_start_time'],
        'identification_start_time': None,
        'review_time': None,
        'indexed': response.json()['indexed'],
        'elasticsearchable': response.json()['elasticsearchable'],
        'jobs': [],
        'speciesDetectionModel': ['african_terrestrial'],
        'unreviewed_start_time': response.json()['unreviewed_start_time'],
    }
    # due to task timing, both are valid
    assert response.json()['stage'] in ['identification', 'un_reviewed']

    # GET sighting
    response = session.get(codex_url(f'/api/v1/sightings/{sighting_guid}'))
    assert response.status_code == 200

    # DELETE asset group
    response = session.delete(codex_url(f'/api/v1/asset_groups/{asset_group_guid}'))
    assert response.status_code == 204


# bulk upload needs existing individuals for encounter assignment
def create_individual(
    session,
    codex_url,
    default_name_val='test zebra',
    default_name_context=DEFAULT_NAME_CONTEXT,
):
    group_data = {
        'description': 'This is a test asset_group, please ignore',
        'uploadType': 'bulk',
        'speciesDetectionModel': ['None'],
        'sightings': [
            {
                'time': '2000-01-01T01:01:01+00:00',
                'timeSpecificity': 'time',
                'locationId': 'PYTEST-SIGHTING',
                'encounters': [{}],
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
    # but do need to wait for it to be un-reviewed
    utils.wait_for(
        session.get, sight_url, lambda response: response.json()['stage'] == 'un_reviewed'
    )
    sight_json = session.get(sight_url).json()
    assert sight_json['stage'] in ['identification', 'un_reviewed']

    encounter_guid = [enc['guid'] for enc in sight_json['encounters']][0]
    indiv_data = {
        'encounters': [{'id': encounter_guid}],
        'names': [
            {'context': default_name_context, 'value': default_name_val},
        ],
    }

    response = session.post(codex_url('/api/v1/individuals/'), json=indiv_data)
    assert response.status_code == 200
    return response


def test_bulk_upload(session, login, codex_url, test_root, request):
    login(session)

    # bulk upload needs existing individuals for encounter assignment
    test_ind_name = 'test zebra'
    test_name_context = DEFAULT_NAME_CONTEXT
    create_individual(session, codex_url, test_ind_name, test_name_context)

    # Create asset group sighting
    transaction_id = utils.upload_to_tus(
        session,
        codex_url,
        list(test_root.glob('turtle*.jpg')),
    )
    response = session.post(
        codex_url('/api/v1/asset_groups/'),
        json={
            'description': 'Bulk import from user',
            'uploadType': 'bulk',
            'speciesDetectionModel': ['african_terrestrial'],
            'transactionId': transaction_id,
            'sightings': [
                {
                    'assetReferences': ['turtle1.jpg'],
                    'decimalLongitude': '73.5622',
                    'decimalLatitude': '4.286',
                    'locationId': 'PYTEST',
                    'verbatimLocality': 'North Male Lankan Reef',
                    'verbatimEventDate': 'yesterday',
                    'time': '2014-01-01T09:00:00.000+00:00',
                    'timeSpecificity': 'time',
                    'encounters': [
                        {
                            'decimalLatitude': '4.286',
                            'decimalLongitude': '73.5622',
                            'verbatimLocality': 'North Male Lankan Reef',
                            'verbatimEventDate': 'yesterday',
                            #'taxonomy': 'ace5e17c-e74a-423f-8bd2-ecc3d7a78f4c',
                            'time': '2014-01-01T09:00:00.000+00:00',
                            'timeSpecificity': 'time',
                            test_name_context: test_ind_name,
                        }
                    ],
                },
                {
                    'assetReferences': ['turtle2.jpg', 'turtle3.jpg'],
                    'decimalLongitude': '73.5622',
                    'decimalLatitude': '4.2861',
                    'locationId': 'PYTEST too',
                    'verbatimLocality': 'North Male Lankan Reef',
                    'verbatimEventDate': 'yesterday',
                    'time': '2014-01-01T09:00:00.000+00:00',
                    'timeSpecificity': 'time',
                    'encounters': [
                        {
                            'decimalLatitude': '4.2861',
                            'decimalLongitude': '73.5622',
                            'verbatimLocality': 'North Male Lankan Reef',
                            'verbatimEventDate': 'yesterday',
                            #'taxonomy': 'ace5e17c-e74a-423f-8bd2-ecc3d7a78f4c',
                            'time': '2014-01-01T09:00:00.000+00:00',
                            'timeSpecificity': 'time',
                        }
                    ],
                },
                {
                    'assetReferences': ['turtle4.jpg', 'turtle5.jpg'],
                    'decimalLongitude': '73.6421',
                    'decimalLatitude': '4.3638',
                    'locationId': 'PYTEST too',
                    'verbatimLocality': 'North Male Gasfinolhu Inside Reef',
                    'time': '2019-01-01T09:00:00.000+00:00',
                    'timeSpecificity': 'time',
                    'encounters': [
                        {
                            'decimalLatitude': '4.3638',
                            'decimalLongitude': '73.6421',
                            'verbatimLocality': 'North Male Gasfinolhu Inside Reef',
                            #'taxonomy': 'ace5e17c-e74a-423f-8bd2-ecc3d7a78f4c',
                            'time': '2019-01-01T09:00:00.000+00:00',
                            'timeSpecificity': 'time',
                        }
                    ],
                },
            ],
        },
    )
    asset_group_guid = response.json()['guid']
    # Delete asset group after test
    request.addfinalizer(
        lambda: session.delete(codex_url(f'/api/v1/asset_groups/{asset_group_guid}'))
    )
    ags_guids = [a['guid'] for a in response.json()['asset_group_sightings']]

    # Wait for detection
    for ags_guid in reversed(ags_guids):
        utils.wait_for(
            session.get,
            codex_url(f'/api/v1/asset_groups/sighting/{ags_guid}'),
            lambda response: response.json()['stage'] == 'curation',
        )

    # Commit asset group sightings
    sighting_guids = []
    for ags_guid in ags_guids:
        response = session.post(
            codex_url(f'/api/v1/asset_groups/sighting/{ags_guid}/commit')
        )
        assert response.status_code == 200
        sighting_guids.append(response.json()['guid'])


def test_delete_asset_group_sightings(session, login, codex_url, test_root, request):
    login(session)

    # Create asset group sighting
    transaction_id = utils.upload_to_tus(
        session,
        codex_url,
        list(test_root.glob('turtle*.jpg')),
    )
    response = session.post(
        codex_url('/api/v1/asset_groups/'),
        json={
            'description': 'Bulk import from user',
            'uploadType': 'bulk',
            'speciesDetectionModel': ['african_terrestrial'],
            'transactionId': transaction_id,
            'sightings': [
                {
                    'assetReferences': ['turtle1.jpg', 'turtle5.jpg'],
                    'locationId': 'PYTEST',
                    'time': '2014-01-01T09:00:00.000+00:00',
                    'timeSpecificity': 'time',
                    'encounters': [{}],
                },
                {
                    'assetReferences': ['turtle2.jpg', 'turtle3.jpg', 'turtle4.jpg'],
                    'locationId': 'PYTEST too',
                    'time': '2014-01-01T09:00:00.000+00:00',
                    'timeSpecificity': 'time',
                    'encounters': [{}],
                },
            ],
        },
    )
    asset_group_guid = response.json()['guid']
    # Delete asset group after test
    request.addfinalizer(
        lambda: session.delete(codex_url(f'/api/v1/asset_groups/{asset_group_guid}'))
    )

    ags_guids = [a['guid'] for a in response.json()['asset_group_sightings']]
    # Delete first asset group sighting
    response = session.delete(
        codex_url(f'/api/v1/asset_groups/sighting/as_sighting/{ags_guids[0]}')
    )
    assert response.status_code == 204

    # GET first asset group sighting should be 404
    response = session.get(
        codex_url(f'/api/v1/asset_groups/sighting/as_sighting/{ags_guids[0]}')
    )
    assert response.status_code == 404

    # GET second asset group sighting and asset group should be 200
    response = session.get(
        codex_url(f'/api/v1/asset_groups/sighting/as_sighting/{ags_guids[1]}')
    )
    assert response.status_code == 200
    response = session.get(codex_url(f'/api/v1/asset_groups/{asset_group_guid}'))
    assert response.status_code == 200

    # Deleting the second (and final) asset group sighting should delete the asset group
    response = session.delete(
        codex_url(f'/api/v1/asset_groups/sighting/as_sighting/{ags_guids[1]}')
    )
    assert response.status_code == 204

    # GET asset group sighting and asset group should be 404
    response = session.get(
        codex_url(f'/api/v1/asset_groups/sighting/as_sighting/{ags_guids[1]}')
    )
    assert response.status_code == 404
    response = session.get(codex_url(f'/api/v1/asset_groups/{asset_group_guid}'))
    assert response.status_code == 404
