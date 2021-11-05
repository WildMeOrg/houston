# -*- coding: utf-8 -*-
from . import utils


def test_sightings(session, login, codex_url, test_root, admin_name):
    login(session)

    response = session.get(codex_url('/api/v1/users/me'))
    my_guid = response.json()['guid']

    # Create sighting
    transaction_id = utils.upload_to_tus(
        session,
        codex_url,
        [test_root / 'zebra.jpg', test_root / 'fluke.jpg'],
    )
    response = session.post(
        codex_url('/api/v1/sightings/'),
        json={
            'locationId': 'PYTEST',
            'startTime': '2000-01-01T01:01:01Z',
            'encounters': [{}, {}],
            'assetReferences': [
                {
                    'transactionId': transaction_id,
                    'path': 'zebra.jpg',
                },
                {
                    'transactionId': transaction_id,
                    'path': 'fluke.jpg',
                },
            ],
        },
    )
    assert response.status_code == 200
    sighting_id = response.json()['result']['id']
    sighting_version = response.json()['result']['version']
    asset_group_guid = response.json()['result']['assets'][0]['asset_group']['guid']
    commit = response.json()['result']['assets'][0]['asset_group']['commit']
    assets = response.json()['result']['assets']
    encounters = response.json()['result']['encounters']
    assert response.json() == {
        'success': True,
        'result': {
            'assets': [
                {
                    'annotations': [],
                    'asset_group': {
                        # b85e93fbc513b37e07225e3fa4566b8d259e9f68
                        'commit': commit,
                        'description': f'Sighting.post {sighting_id}',
                        'guid': asset_group_guid,
                        'major_type': 'filesystem',
                    },
                    # 2021-11-08T11:30:40.106173+00:00
                    'created': assets[0]['created'],
                    # {'height': 667, 'width': 1000}
                    'dimensions': assets[0]['dimensions'],
                    'filename': assets[0]['filename'],  # fluke.jpg
                    'guid': assets[0]['guid'],
                    'src': f'/api/v1/assets/src/{assets[0]["guid"]}',
                    # 2021-11-08T11:30:40.106173+00:00
                    'updated': assets[0]['updated'],
                },
                {
                    'annotations': [],
                    'asset_group': {
                        'commit': commit,
                        'description': f'Sighting.post {sighting_id}',
                        'guid': asset_group_guid,
                        'major_type': 'filesystem',
                    },
                    # 2021-11-08T11:30:40.106173+00:00
                    'created': assets[1]['created'],
                    # {'height': 664, 'width': 1000}
                    'dimensions': assets[1]['dimensions'],  # zebra.jpg
                    'filename': assets[1]['filename'],
                    'guid': assets[1]['guid'],
                    'src': f'/api/v1/assets/src/{assets[1]["guid"]}',
                    # 2021-11-08T11:30:40.106173+00:00
                    'updated': assets[1]['updated'],
                },
            ],
            'encounters': [
                {
                    'id': encounters[0]['id'],  # 12816b99-d934-4e64-aa68-ace3ad83bc62
                    'version': encounters[0]['version'],  # 1636148722833
                },
                {
                    'id': encounters[1]['id'],
                    'version': encounters[1]['version'],
                },
            ],
            'id': sighting_id,
            'version': sighting_version,
        },
    }
    assert set(a['filename'] for a in assets) == {'fluke.jpg', 'zebra.jpg'}

    # GET sighting
    response = session.get(codex_url(f'/api/v1/sightings/{sighting_id}'))
    detailed_encounters = response.json()['encounters']
    assert response.status_code == 200
    assert response.json() == {
        'assets': [
            {
                'annotations': [],
                # 2021-11-08T11:30:40.106173+00:00
                'created': assets[0]['created'],
                # {'height': 667, 'width': 1000}
                'dimensions': assets[0]['dimensions'],
                'filename': assets[0]['filename'],  # fluke.jpg
                'guid': assets[0]['guid'],
                'src': f'/api/v1/assets/src/{assets[0]["guid"]}',
                # 2021-11-08T11:30:40.106173+00:00
                'updated': assets[0]['updated'],
            },
            {
                'annotations': [],
                # 2021-11-08T11:30:40.106173+00:00
                'created': assets[1]['created'],
                # {'height': 664, 'width': 1000}
                'dimensions': assets[1]['dimensions'],
                'filename': assets[1]['filename'],  # zebra.jpg
                'guid': assets[1]['guid'],
                'src': f'/api/v1/assets/src/{assets[1]["guid"]}',
                # 2021-11-08T11:30:40.106173+00:00
                'updated': assets[1]['updated'],
            },
        ],
        'comments': 'None',
        # 2021-11-05T21:50:19.963476+00:00
        'createdEDM': response.json()['createdEDM'],
        # 2021-11-05T21:50:19.963497+00:00
        'createdHouston': response.json()['createdHouston'],
        'customFields': {},
        'encounters': [
            {
                # 2021-11-05T21:50:19.973753+00:00
                'createdHouston': detailed_encounters[0]['createdHouston'],
                'customFields': {},
                'guid': encounters[0]['id'],
                'hasEdit': True,
                'hasView': True,
                'id': encounters[0]['id'],
                'individual': {},
                'owner': {
                    'guid': my_guid,
                    'full_name': admin_name,
                    'profile_fileupload': None,
                },
                'submitter': {
                    'guid': my_guid,
                    'full_name': admin_name,
                    'profile_fileupload': None,
                },
                'timeValues': [None, None, None, 0, 0],
                'updatedHouston': detailed_encounters[0]['updatedHouston'],
                'version': encounters[0]['version'],
            },
            {
                'createdHouston': detailed_encounters[1]['createdHouston'],
                'customFields': {},
                'guid': encounters[1]['id'],
                'hasEdit': True,
                'hasView': True,
                'id': encounters[1]['id'],
                'individual': {},
                'owner': {
                    'guid': my_guid,
                    'full_name': admin_name,
                    'profile_fileupload': None,
                },
                'submitter': {
                    'guid': my_guid,
                    'full_name': admin_name,
                    'profile_fileupload': None,
                },
                'timeValues': [None, None, None, 0, 0],
                'updatedHouston': detailed_encounters[1]['updatedHouston'],
                'version': encounters[1]['version'],
            },
        ],
        'encounterCounts': {
            'individuals': 0,
            'lifeStage': {},
            'sex': {},
        },
        'featuredAssetGuid': assets[0]['guid'],
        'guid': sighting_id,
        'hasEdit': True,
        'hasView': True,
        'id': sighting_id,
        'locationId': 'PYTEST',
        'startTime': '2000-01-01T01:01:01Z',
        'updatedHouston': response.json()['updatedHouston'],
        'version': sighting_version,
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
    assert response.json()['result']['version'] > sighting_version
    sighting_version = response.json()['result']['version']
    assert response.json() == {
        'result': {
            'comments': 'None',
            'createdEDM': response.json()['result']['createdEDM'],
            'encounters': [
                {
                    'id': encounters[0]['id'],
                    'version': encounters[0]['version'],
                },
                {
                    'id': encounters[1]['id'],
                    'version': encounters[1]['version'],
                },
            ],
            'id': sighting_id,
            'startTime': '2000-01-01T01:01:01Z',
            'version': sighting_version,
        },
        'patchResults': [
            {
                'op': 'add',
                'path': 'decimalLatitude',
                'value': 52.152029,
            },
            {
                'op': 'add',
                'path': 'decimalLongitude',
                'value': 2.318116,
            },
        ],
        'success': True,
        # 6c152f7e-4613-4acc-b44f-2fe278bee9dd
        'transactionId': response.json()['transactionId'],
    }
