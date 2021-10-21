# -*- coding: utf-8 -*-
import time

from .utils import upload_to_tus


def test_create_asset_group_detection(session, codex_url, test_root, login):
    login(session)
    me = session.get(codex_url('/api/v1/users/me')).json()
    zebra = test_root / 'zebra.jpg'
    transaction_id = upload_to_tus(session, codex_url, zebra)
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

    asset_group = response.json()
    asset_guids = [asset['guid'] for asset in asset_group['assets']]
    ags_guids = [ags['guid'] for ags in asset_group['asset_group_sightings']]

    assert response.json() == {
        'commit': asset_group['commit'],
        'created': asset_group['created'],
        'updated': asset_group['updated'],
        'assets': [
            {
                'src': f'/api/v1/assets/src/{asset_guids[0]}',
                'filename': 'zebra.jpg',
                'guid': asset_guids[0],
            },
        ],
        'asset_group_sightings': [{'guid': ags_guids[0]}],
        'major_type': 'filesystem',
        'description': 'This is a test asset_group, please ignore',
        'owner_guid': me['guid'],
        'guid': asset_group['guid'],
    }

    timeout = 2400  # timeout after 20 minutes
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

    response_json = response.json()
    job_id = list(response_json['jobs'].keys())[0]
    first_job = response_json['jobs'][job_id]
    job_start = first_job['start']
    annotation_uuids = [
        annot['uuid']['__UUID__'] for annot in first_job['json_result']['results_list'][0]
    ]
    assert response_json == {
        'assets': [
            {
                'guid': asset_guids[0],
                'src': f'/api/v1/assets/src/{asset_guids[0]}',
                'filename': 'zebra.jpg',
            }
        ],
        'completion': 10,
        'stage': 'curation',
        'jobs': {
            job_id: {
                'model': 'african_terrestrial',
                'active': False,
                'start': job_start,
                'asset_ids': asset_guids,
                'json_result': {
                    'image_uuid_list': [
                        {
                            '__UUID__': '90917c9d-6e50-3b28-7396-c08f77f0c7eb',
                        },
                    ],
                    'results_list': [
                        [
                            {
                                'id': 1,
                                'uuid': {'__UUID__': annotation_uuids[0]},
                                'xtl': 178,
                                'ytl': 72,
                                'left': 178,
                                'top': 72,
                                'width': 604,
                                'height': 534,
                                'theta': 0.0,
                                'confidence': 0.9185,
                                'class': 'zebra_plains',
                                'species': 'zebra_plains',
                                'viewpoint': None,
                                'quality': None,
                                'multiple': False,
                                'interest': False,
                            }
                        ],
                    ],
                    'score_list': [0.0],
                    'has_assignments': False,
                },
            },
        },
        'config': {
            'startTime': response_json['config']['startTime'],
            'locationId': 'Tiddleywink',
            'encounters': response_json['config']['encounters'],
            'assetReferences': ['zebra.jpg'],
        },
        'guid': ags_guids[0],
    }
