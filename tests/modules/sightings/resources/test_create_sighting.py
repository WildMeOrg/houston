# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.asset_groups.resources import utils as asset_group_utils
from tests.extensions.tus import utils as tus_utils
from tests import utils as test_utils
import datetime
import pytest

from tests.utils import module_unavailable

timestamp = datetime.datetime.now().isoformat() + 'Z'


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_get_sighting_not_found(flask_app_client):
    response = flask_app_client.get('/api/v1/sightings/wrong-uuid')
    assert response.status_code == 404
    response.close()


@pytest.mark.skipif(
    module_unavailable('sightings', 'encounters'), reason='Sightings module disabled'
)
def test_create_failures(flask_app_client, test_root, researcher_1, request):

    # empty data_in will fail (no location ID)
    data_in = {'foo': 'bar'}
    expected_error = 'locationId field missing from Sighting 1'
    sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, data_in, 400, expected_error
    )

    data_in = {'locationId': 'wibble', 'startTime': timestamp}
    expected_error = 'encounters field missing from Sighting 1'
    sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, data_in, 400, expected_error
    )

    # has encounters, but bunk assetReferences
    data_in = {
        'encounters': [{}],
        'startTime': timestamp,
        'assetReferences': [{'fail': 'fail'}],
        'context': 'test',
        'locationId': 'test',
    }
    expected_error = "Invalid assetReference data {'fail': 'fail'}"
    sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, data_in, 400, expected_error
    )

    # assetReferences, but no files for them
    data_in['assetReferences'][0] = {
        'path': 'i-dont-exist.jpg',
    }
    expected_error = "Invalid assetReference data {'path': 'i-dont-exist.jpg'}"
    sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, data_in, 400, expected_error
    )


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_create_and_modify_and_delete_sighting(
    db, flask_app_client, researcher_1, test_root, staff_user, request
):
    from app.modules.sightings.models import Sighting

    # we should end up with these same counts (which _should be_ all zeros!)
    orig_ct = test_utils.all_count(db)
    data_in = {
        'encounters': [{}, {}],
        'startTime': timestamp,
        'context': 'test',
        'locationId': 'test',
    }
    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, data_in
    )

    sighting_id = uuids['sighting']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None
    assert len(uuids['encounters']) == 2
    enc0_id = uuids['encounters'][0]
    enc1_id = uuids['encounters'][1]
    assert enc0_id is not None
    assert enc1_id is not None

    sighting_utils.read_sighting(flask_app_client, researcher_1, sighting_id)

    # test to see if we grew by 1 sighting and 2 encounters
    ct = test_utils.all_count(db)
    assert ct['Sighting'] == orig_ct['Sighting'] + 1
    assert ct['Encounter'] == orig_ct['Encounter'] + 2

    # test some simple modification (should succeed)
    new_loc_id = 'test_2'
    sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'replace', 'path': '/locationId', 'value': new_loc_id},
        ],
    )
    # check that change was made
    response = sighting_utils.read_sighting(flask_app_client, researcher_1, sighting_id)
    assert response.json['locationId'] == new_loc_id

    # test some modification (should fail due to invalid data)
    sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'add', 'path': '/decimalLatitude', 'value': 999.9},
        ],
        expected_status_code=400,
    )

    # patch op=add will create a new (3rd) encounter
    sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {
                'op': 'add',
                'path': '/encounters',
                'value': {'locationId': 'encounter_patch_add'},
            }
        ],
    )
    # test to see if we now are +1 encounter
    ct = test_utils.all_count(db)
    assert ct['Encounter'] == orig_ct['Encounter'] + 3  # previously was + 2
    assert len(sighting.encounters) == 3
    enc0_id, enc1_id, enc2_id = [str(e.guid) for e in sighting.encounters]

    # patch op=remove the one we just added to get us back to where we started
    sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'remove', 'path': '/encounters', 'value': enc2_id},
        ],
    )
    assert len(sighting.encounters) == 2
    # test to see if we now are back to where we started
    ct = test_utils.all_count(db)
    assert ct['Encounter'] == orig_ct['Encounter'] + 2

    # patch op=remove the first encounter; should succeed no problem cuz there is one enc remaining
    sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'remove', 'path': '/encounters', 'value': enc0_id},
        ],
    )
    # test to see if we now are -1 encounter
    ct = test_utils.all_count(db)
    assert ct['Encounter'] == orig_ct['Encounter'] + 1  # previously was + 2

    # similar to above, but this should fail as this is our final encounter, and thus cascade-deletes the occurrence
    #  -- and this requires confirmation
    response = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'remove', 'path': '/encounters', 'value': enc1_id},
        ],
        expected_status_code=400,
    )
    assert response.json['edm_status_code'] == 602, response.json
    # should still have same number encounters as above here
    ct = test_utils.all_count(db)
    assert ct['Encounter'] == orig_ct['Encounter'] + 1

    # now we try again, but this time with header to allow for cascade deletion of sighting
    sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'remove', 'path': '/encounters', 'value': enc1_id},
        ],
        headers=(('x-allow-delete-cascade-sighting', True),),
    )
    # now this should bring us back to where we started
    ct = test_utils.all_count(db)
    assert ct == orig_ct


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_create_anon_and_delete_sighting(
    db, flask_app_client, researcher_1, staff_user, test_root, request
):
    from app.modules.sightings.models import Sighting

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    request.addfinalizer(lambda: tus_utils.cleanup_tus_dir(transaction_id))
    tus_utils.prep_tus_dir(test_root, filename='fluke.jpg')
    sighting_data = {
        'startTime': timestamp,
        'context': 'test',
        'locationId': 'test',
        'encounters': [{}],
        'assetReferences': [test_filename, 'fluke.jpg'],
    }
    group_data = {
        'description': 'This is an anonymous asset_group, please ignore',
        'uploadType': 'form',
        'speciesDetectionModel': [
            'None',
        ],
        'transactionId': transaction_id,
        'sightings': [
            sighting_data,
        ],
    }
    group_create_response = asset_group_utils.create_asset_group(
        flask_app_client, None, group_data
    )
    group_guid = group_create_response.json['guid']
    request.addfinalizer(
        lambda: asset_group_utils.delete_asset_group(
            flask_app_client, staff_user, group_guid
        )
    )
    assets = sorted(group_create_response.json['assets'], key=lambda a: a['filename'])
    asset_guids = [a['guid'] for a in assets]
    assert assets[0]['filename'] == 'fluke.jpg'
    assert assets[0]['guid'] == asset_guids[0]
    assert assets[0]['src'] == f'/api/v1/assets/src/{asset_guids[0]}'
    assert assets[1]['filename'] == 'zebra.jpg'
    assert assets[1]['guid'] == asset_guids[1]
    assert assets[1]['src'] == f'/api/v1/assets/src/{asset_guids[1]}'

    asset_group_sighting_guid = group_create_response.json['asset_group_sightings'][0][
        'guid'
    ]
    commit_resp = asset_group_utils.commit_asset_group_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid
    )
    sighting_id = commit_resp.json['guid']
    # Check sighting and assets are stored in the database
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None
    asset_guids.sort()
    assert sorted([str(a.asset_guid) for a in sighting.sighting_assets]) == asset_guids

    # Check assets are returned in GET sighting
    with flask_app_client.login(staff_user, auth_scopes=('sightings:read',)):
        response = flask_app_client.get(f'/api/v1/sightings/{sighting_id}')
        assert sorted([a['guid'] for a in response.json['assets']]) == asset_guids

    # test some modification; this should fail (401) cuz anon should not be allowed
    new_loc_id = 'test_2_fail'
    sighting_utils.patch_sighting(
        flask_app_client,
        None,
        sighting_id,
        patch_data=[
            {'op': 'replace', 'path': '/locationId', 'value': new_loc_id},
        ],
        expected_status_code=401,
    )


@pytest.mark.skipif(
    module_unavailable('sightings', 'encounters'), reason='Sightings module disabled'
)
def test_edm_and_houston_encounter_data_within_sightings(
    db, flask_app_client, researcher_1, staff_user, request, test_root
):

    json = None
    individual_json = None
    try:
        data_in = {
            'startTime': timestamp,
            'context': 'test',
            'locationId': 'test',
            'encounters': [
                {
                    'locationId': 'Saturn',
                    'decimalLatitude': 25.9999,
                    'decimalLongitude': 25.9999,
                    'verbatimLocality': 'Saturn',
                    'time': '2010-01-01T01:01:01Z',
                },
            ],
        }
        uuids = sighting_utils.create_sighting(
            flask_app_client, researcher_1, request, test_root, data_in
        )
        sighting_guid = uuids['sighting']

        response = sighting_utils.read_sighting(
            flask_app_client,
            researcher_1,
            sighting_guid,
            expected_status_code=200,
        )
        json = response.json

        # EDM stuff
        assert json['encounters'][0]['verbatimLocality'] == 'Saturn'
        assert json['encounters'][0]['locationId'] == 'Saturn'
        assert json['encounters'][0]['time'] == '2010-01-01T01:01:01Z'
        assert json['encounters'][0]['decimalLatitude'] == 25.9999
        assert json['encounters'][0]['decimalLongitude'] == 25.9999

        # houston stuff
        assert json['encounters'][0]['id'] is not None

        enc_id = json['encounters'][0]['id']

        assert json['encounters'][0]['hasView'] is True
        assert json['encounters'][0]['hasEdit'] is True

        individual_data_in = {
            'names': {
                'defaultName': 'Micheal Aday',
                'nickname': 'Meatloaf',
            },
            'encounters': [{'id': str(enc_id)}],
        }

        individual_response = individual_utils.create_individual(
            flask_app_client, researcher_1, 200, individual_data_in
        )

        assert individual_response.json['result']['id'] is not None

        individual_id = individual_response.json['result']['id']

        individual_json = individual_utils.read_individual(
            flask_app_client, researcher_1, individual_id
        ).json

        assert individual_json['names']['defaultName'] == 'Micheal Aday'
        assert individual_json['names']['nickname'] == 'Meatloaf'

        # some duplication, but I wanted to check the sighting/encounter data first before complexifying it
        response = sighting_utils.read_sighting(
            flask_app_client,
            researcher_1,
            response.json['id'],
            expected_status_code=200,
        )
        json = response.json

        assert json['encounters'][0]['individual'] is not None
        assert json['encounters'][0]['individual']['id'] == individual_id
        assert json['encounters'][0]['individual']['names'] is not None
        assert (
            json['encounters'][0]['individual']['names']['defaultName'] == 'Micheal Aday'
        )
        assert json['encounters'][0]['individual']['names']['nickname'] == 'Meatloaf'

    finally:
        individual_utils.delete_individual(
            flask_app_client, staff_user, individual_json['id']
        )
