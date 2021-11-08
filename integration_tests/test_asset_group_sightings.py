# -*- coding: utf-8 -*-
import time

from . import utils


def test_asset_group_sightings(session, login, codex_url, test_root):
    login(session)

    response = session.get(codex_url('/api/v1/users/me'))
    my_guid = response.json()['guid']

    # Create asset group sighting
    transaction_id = utils.upload_to_tus(
        session,
        codex_url,
        [test_root / 'zebra.jpg'],
    )
    response = session.post(
        codex_url('/api/v1/asset_groups/'),
        json={
            'description': 'This is a test asset group, please ignore',
            'uploadType': 'form',
            'speciesDetectionModel': ['african_terrestrial'],
            'transactionId': transaction_id,
            'sightings': [
                {
                    'startTime': '2000-01-01T01:01:01Z',
                    'locationId': 'PYTEST',
                    # There can only be one encounter
                    'encounters': [{}],
                    'assetReferences': ['zebra.jpg'],
                },
            ],
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
    timeout = 4 * 60  # timeout after 4 minutes
    ags_url = codex_url(f'/api/v1/asset_groups/sighting/{ags_guids[0]}')

    try:
        while timeout >= 0:
            response = session.get(ags_url)
            assert response.status_code == 200
            if response.json()['stage'] != 'detection':
                break
            time.sleep(15)
            timeout -= 15
        if response.json()['stage'] != 'curation':
            assert (
                False
            ), f'{timeout <= 0 and "Timed out: " or ""}stage={response.json()["stage"]}\n{response.json()}'
    except KeyboardInterrupt:
        print(f'The last response from {ags_url}:\n{response.json()}')
        raise

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
        'encounters': [{'guid': encounter_guids[0]}],
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
        'encounters': [{'guid': encounter_guids[0]}],
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
