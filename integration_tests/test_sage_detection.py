# -*- coding: utf-8 -*-
from . import utils


def test_create_asset_group_detection(session, codex_url, test_root, login):
    login(session)
    me = session.get(codex_url('/api/v1/users/me')).json()

    # Create asset group
    zebra = test_root / 'zebra.jpg'
    transaction_id = utils.upload_to_tus(session, codex_url, [zebra])
    data = {
        'description': 'This is a test asset_group, please ignore',
        'uploadType': 'form',
        'speciesDetectionModel': ['african_terrestrial'],
        'transactionId': transaction_id,
        'sightings': [
            {
                'startTime': '2000-01-01T01:01:01Z',
                'locationId': 'Tiddleywink',
                'encounters': [{}],
                'assetReferences': [zebra.name],
            },
        ],
    }
    response = session.post(
        codex_url('/api/v1/asset_groups/'),
        json=data,
    )
    assert response.status_code == 200
    asset_group_guid = response.json()['guid']
    assert len(response.json()['assets']) == 1
    asset_guid = response.json()['assets'][0]['guid']
    assert len(response.json()['asset_group_sightings']) == 1
    ags_guid = response.json()['asset_group_sightings'][0]['guid']

    # Asset group sighting test validates the response so don't duplicate here

    # Wait for sage detection and GET asset group sighting
    ags_url = codex_url(f'/api/v1/asset_groups/sighting/{ags_guid}')
    response = utils.wait_for(
        session.get, ags_url, lambda response: response.json()['stage'] == 'curation'
    )

    response_json = response.json()
    first_job = response_json['jobs'][0]

    assert response_json == {
        'assets': [
            {
                'guid': asset_guid,
                'src': f'/api/v1/assets/src/{asset_guid}',
                'filename': 'zebra.jpg',
                'annotations': response_json['assets'][0]['annotations'],
                'created': response_json['assets'][0]['created'],
                'updated': response_json['assets'][0]['updated'],
                'dimensions': {
                    'height': 664,
                    'width': 1000,
                },
            }
        ],
        'completion': 10,
        'stage': 'curation',
        'jobs': [
            {
                'job_id': first_job['job_id'],
                'model': 'african_terrestrial',
                'active': False,
                'start': first_job['start'],
                'asset_ids': asset_guids,
            },
        ],
        'config': {
            'startTime': response_json['config']['startTime'],
            'locationId': 'Tiddleywink',
            'encounters': response_json['config']['encounters'],
            'assetReferences': ['zebra.jpg'],
        },
        'guid': ags_guid,
        'curation_start_time': response.json()['curation_start_time'],
        'detection_start_time': response.json()['detection_start_time'],
        'asset_group_guid': asset_group_guid,
        'sighting_guid': None,
        'creator': {
            'full_name': 'Test admin',
            'guid': me['guid'],
            'profile_fileupload': None,
        },
    }

    # DELETE asset group
    response = session.delete(codex_url(f'/api/v1/asset_groups/{asset_group_guid}'))
    assert response.status_code == 204
