# -*- coding: utf-8 -*-
from . import utils


# Not a generic util as there has to be exactly one asset group sighting, asset, sighting, encounter,
# annotation and encounter
def create_sighting(session, codex_url, test_root, filename):
    transaction_id = utils.upload_to_tus(session, codex_url, [test_root / filename])
    group_data = {
        'description': 'This is a test asset_group, please ignore',
        'uploadType': 'form',
        'speciesDetectionModel': ['african_terrestrial'],
        'transactionId': transaction_id,
        'sightings': [
            {
                'startTime': '2000-01-01T01:01:01Z',
                'locationId': 'Tiddleywink',
                'encounters': [{}],
                'assetReferences': [filename],
                'idConfigs': [
                    {
                        'matchingSetDataOwners': 'all',
                        'algorithms': ['hotspotter_nosv'],
                    }
                ],
            },
        ],
    }
    asset_group_guid, asset_group_sighting_guids, asset_guids = utils.create_asset_group(
        session, codex_url, group_data
    )
    assert len(asset_group_sighting_guids) == 1
    ags_guid = asset_group_sighting_guids[0]
    assert len(asset_guids) == 1

    annotation_guids, encounter_guids = utils.wait_for_sighting_detection_complete(
        session, codex_url, ags_guid
    )
    assert len(annotation_guids) == 1
    annot_guid = annotation_guids[0]
    assert len(encounter_guids) == 1
    encounter_guid = encounter_guids[0]

    # We got an annotation back, need to add it to the encounter in the sighting
    patch_response = session.patch(
        codex_url(f'/api/v1/asset_groups/sighting/{ags_guid}/encounter/{encounter_guid}'),
        json=[{'op': 'add', 'path': '/annotations', 'value': [annot_guid]}],
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
    # WIP response guids to be used
    create_sighting(session, codex_url, test_root, 'zebra.jpg')
    create_sighting(session, codex_url, test_root, 'phoenix.jpg')
