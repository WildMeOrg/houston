# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import datetime
import uuid

import pytest

from tests import utils as test_utils
from tests.extensions.tus import utils as tus_utils
from tests.modules.asset_groups.resources import utils as asset_group_utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
from tests.utils import module_unavailable

timestamp = test_utils.isoformat_timestamp_now()

valid_lat = 25.9999
valid_long = 25.9999


# Used in multiple tests so only have it once, but needs to be a function, not static data as the
# autouse function that creates the regions is run before this is called
def get_saturn_data():

    return {
        'time': timestamp,
        'timeSpecificity': 'time',
        'locationId': test_utils.get_valid_location_id(),
        'encounters': [
            {
                'locationId': test_utils.get_valid_location_id(),
                'decimalLatitude': valid_lat,
                'decimalLongitude': valid_long,
                'verbatimLocality': 'Saturn',
                'time': '2010-01-01T01:01:01+00:00',
                'timeSpecificity': 'time',
            },
        ],
    }


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

    data_in = {
        'locationId': test_utils.get_valid_location_id(),
        'time': timestamp,
        'timeSpecificity': 'time',
    }
    expected_error = 'encounters field missing from Sighting 1'
    sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, data_in, 400, expected_error
    )

    # has encounters, but bunk assetReferences
    data_in = {
        'encounters': [{}],
        'time': timestamp,
        'timeSpecificity': 'time',
        'assetReferences': [{'fail': 'fail'}],
        'locationId': test_utils.get_valid_location_id(),
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
    import tests.modules.site_settings.resources.utils as site_setting_utils
    from app.modules.complex_date_time.models import Specificities
    from app.modules.sightings.models import Sighting

    regions = site_setting_utils.get_and_ensure_test_regions(flask_app_client, staff_user)
    region2_id = regions[1]['id']

    # we should end up with these same counts (which _should be_ all zeros!)
    orig_ct = test_utils.all_count(db)
    data_in = {
        'encounters': [{}, {}],
        'time': timestamp,
        'timeSpecificity': 'time',
        'locationId': test_utils.get_valid_location_id(),
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
    sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'replace', 'path': '/locationId', 'value': region2_id},
            {'op': 'replace', 'path': '/match_state', 'value': 'reviewed'},
        ],
    )
    # check that change was made
    response = sighting_utils.read_sighting(flask_app_client, researcher_1, sighting_id)
    assert response.json['locationId'] == region2_id
    assert response.json['match_state'] == 'reviewed'

    new_configs = [{'algorithms': ['hotspotter_nosv']}]
    sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'replace', 'path': '/idConfigs', 'value': new_configs},
        ],
    )
    # check that change was made
    response = sighting_utils.read_sighting(flask_app_client, researcher_1, sighting_id)
    assert response.json['idConfigs'] == new_configs

    # Single test that Sighting response has the correct keys
    assert set(response.json.keys()) >= {
        'comments',
        'encounters',
        'customFields',
        'locationId',
        'time',
        'timeSpecificity',
        'hasView',
        'updated',
        'identification_start_time',
        'review_time',
        'stage',
        'updated',
        'guid',
        'hasEdit',
        'assets',
        'created',
        'featuredAssetGuid',
        'unreviewed_start_time',
        'creator',
        'match_state',
        'curation_start_time',
        'detection_start_time',
    }

    # some time-related patching -- invalid specificity (should fail w/409)
    patch_data = [
        test_utils.patch_replace_op('timeSpecificity', 'fubar'),
    ]
    patch_res = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data,
        expected_status_code=409,
    )
    assert patch_res.json.get('message') == 'invalid specificity: fubar'

    # should be sufficient to set a (new) time
    test_dt = '1999-01-01T12:34:56-07:00'
    patch_data = [
        test_utils.patch_replace_op('time', test_dt),
        test_utils.patch_replace_op('timeSpecificity', 'month'),
    ]
    patch_res = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data,
    )
    test_sight = Sighting.query.get(sighting_id)
    assert test_sight.time
    assert test_sight.time.specificity == Specificities.month
    assert test_sight.time.timezone == 'UTC-0700'
    assert test_sight.time.isoformat_in_timezone() == test_dt

    # now update just the specificity
    patch_data = [
        test_utils.patch_replace_op('timeSpecificity', 'day'),
    ]
    patch_res = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data,
    )
    test_sight = Sighting.query.get(sighting_id)
    assert test_sight.time
    assert test_sight.time.specificity == Specificities.day
    assert test_sight.time.isoformat_in_timezone() == test_dt

    # now update just the date/time
    test_dt = datetime.datetime.utcnow().isoformat() + '+03:00'
    patch_data = [
        test_utils.patch_replace_op('time', test_dt),
    ]
    patch_res = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data,
    )
    test_sight = Sighting.query.get(sighting_id)
    assert test_sight.time
    assert test_sight.time.specificity == Specificities.day
    assert test_sight.time.timezone == 'UTC+0300'
    assert test_sight.time.isoformat_in_timezone() == test_dt

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

    # invalid match_state
    sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'add', 'path': '/match_state', 'value': 'failure'},
        ],
        expected_status_code=409,
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
                'value': {'locationId': test_utils.get_valid_location_id()},
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
        'time': timestamp,
        'timeSpecificity': 'time',
        'locationId': test_utils.get_valid_location_id(),
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
    assert sorted(str(a.asset_guid) for a in sighting.sighting_assets) == asset_guids

    # Check assets are returned in GET sighting
    with flask_app_client.login(staff_user, auth_scopes=('sightings:read',)):
        response = flask_app_client.get(f'/api/v1/sightings/{sighting_id}')
        assert sorted(a['guid'] for a in response.json['assets']) == asset_guids

    # test some modification; this should fail (401) cuz anon should not be allowed
    new_loc_id = test_utils.get_valid_location_id(1)
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
    db,
    flask_app_client,
    researcher_1,
    staff_user,
    request,
    test_root,
):

    json = None
    try:
        uuids = sighting_utils.create_sighting(
            flask_app_client, researcher_1, request, test_root, get_saturn_data()
        )
        sighting_guid = uuids['sighting']

        response = sighting_utils.read_sighting(
            flask_app_client,
            researcher_1,
            sighting_guid,
            expected_status_code=200,
        )
        json = response.json

        assert json['encounters'][0]['verbatimLocality'] == 'Saturn'
        assert json['encounters'][0]['time'] == '2010-01-01T01:01:01+00:00'
        assert json['encounters'][0]['timeSpecificity'] == 'time'
        assert json['encounters'][0]['decimalLatitude'] == 25.9999
        assert json['encounters'][0]['decimalLongitude'] == 25.9999
        assert json['encounters'][0]['guid'] is not None

        enc_id = json['encounters'][0]['guid']

        assert json['encounters'][0]['hasView'] is True
        assert json['encounters'][0]['hasEdit'] is True

        individual_data_in = {
            'names': [
                {'context': 'defaultName', 'value': 'Michael Aday'},
                {'context': 'nickname', 'value': 'Meatloaf'},
            ],
            'encounters': [{'id': str(enc_id)}],
        }

        individual_response = individual_utils.create_individual(
            flask_app_client, researcher_1, 200, individual_data_in
        )

        assert individual_response.json['guid'] is not None

        individual_id = individual_response.json['guid']

        # now that individual exists, read individual data off *sighting*
        response = sighting_utils.read_sighting(
            flask_app_client,
            researcher_1,
            sighting_guid,
            expected_status_code=200,
        )

        sight_enc_individual = response.json['encounters'][0]['individual']
        assert sight_enc_individual is not None
        assert sight_enc_individual['guid'] == individual_id
        assert len(sight_enc_individual['names']) == 2
        assert sight_enc_individual['names'][0]['context'] == 'defaultName'
        assert sight_enc_individual['names'][0]['value'] == 'Michael Aday'
        assert sight_enc_individual['names'][1]['context'] == 'nickname'
        assert sight_enc_individual['names'][1]['value'] == 'Meatloaf'

    finally:
        individual_utils.delete_individual(flask_app_client, staff_user, individual_id)


# This is now disabled, so make sure that it is
@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_create_old_sighting(flask_app_client, researcher_1):
    error = 'Not supported. Use the AssetGroup POST API instead'
    sighting_utils.create_old_sighting(
        flask_app_client, researcher_1, get_saturn_data(), 400, error
    )


# with edm gone this is kind of just redundant/bonus testing
@pytest.mark.skipif(
    module_unavailable('sightings', 'encounters'), reason='Sightings module disabled'
)
def test_complex_misc_patch(
    db, flask_app_client, researcher_1, staff_user, request, test_root
):

    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, get_saturn_data()
    )
    sighting_guid = uuids['sighting']

    # test some EDM modification (should fail due to invalid data)
    patch_resp = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_guid,
        patch_data=[
            {'op': 'add', 'path': '/decimalLongitude', 'value': 25.9998},
            {'op': 'add', 'path': '/decimalLatitude', 'value': 999.9},
        ],
        expected_status_code=400,
    ).json
    assert patch_resp['message'] == 'decimalLatitude value passed (999.9) is invalid'

    # And neither value changed
    read_resp = sighting_utils.read_sighting(
        flask_app_client,
        researcher_1,
        sighting_guid,
    ).json

    assert read_resp['encounters'][0]['decimalLatitude'] == valid_lat
    assert read_resp['encounters'][0]['decimalLongitude'] == valid_long

    # Same with houston only fields, some work, some fail, all are rolled back
    test_dt = '1999-01-01T12:34:56-07:00'

    patch_resp = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_guid,
        patch_data=[
            {'op': 'replace', 'path': '/time', 'value': test_dt},
            {'op': 'replace', 'path': '/timeSpecificity', 'value': 'fubar'},
        ],
        expected_status_code=409,
    )
    read_resp = sighting_utils.read_sighting(
        flask_app_client,
        researcher_1,
        sighting_guid,
    )
    assert patch_resp.json['message'] == 'invalid specificity: fubar'
    assert read_resp.json['time'] == timestamp

    # we do not support adding of encounter by guid, so this should fail
    patch_resp = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_guid,
        patch_data=[
            {'op': 'replace', 'path': '/time', 'value': test_dt},
            # {'op': 'replace', 'path': '/timeSpecificity', 'value': 'fubar'},
            {'op': 'replace', 'path': '/decimalLongitude', 'value': 24.9999},
            {'op': 'add', 'path': '/encounters', 'value': str(uuid.uuid4())},
        ],
        expected_status_code=400,
    )
    read_resp = sighting_utils.read_sighting(
        flask_app_client,
        researcher_1,
        sighting_guid,
    ).json
    assert read_resp['decimalLongitude'] is None


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_create_sighting_time_test(
    flask_app, flask_app_client, researcher_1, request, test_root
):
    from app.modules.complex_date_time.models import Specificities
    from app.modules.sightings.models import Sighting
    from tests.modules.sightings.resources import utils as sighting_utils

    # test with invalid time
    sighting_data = {
        'time': 'fubar',
        'timeSpecificity': 'time',
        'locationId': test_utils.get_valid_location_id(),
        'encounters': [{}],
    }
    sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
        expected_status_code=400,
        expected_error='time field is not a valid datetime: fubar',
    )

    # now ok, but missing timezone
    sighting_data['time'] = '1999-12-31T23:59:59'
    sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
        expected_status_code=400,
        expected_error=f"timezone cannot be derived from time: {sighting_data['time']}",
    )

    # timezone included, but no specificity
    sighting_data['time'] = '1999-12-31T23:59:59+03:00'
    del sighting_data['timeSpecificity']
    sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
        expected_status_code=400,
        expected_error='timeSpecificity field missing from Sighting 1',
    )

    # getting closer; bad specificity
    sighting_data['timeSpecificity'] = 'fubar'
    sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
        expected_status_code=400,
        expected_error='timeSpecificity fubar not supported',
    )

    # finally; ok
    sighting_data['timeSpecificity'] = 'day'
    uuids = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
        expected_status_code=200,
    )
    assert uuids
    test_sight = Sighting.query.get(uuids['sighting'])
    assert test_sight
    assert test_sight.time
    assert test_sight.time.timezone == 'UTC+0300'
    assert test_sight.time.specificity == Specificities.day
    assert test_sight.time.isoformat_in_timezone() == sighting_data['time']


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_admin_user(db, flask_app_client, researcher_1, test_root, admin_user, request):
    from app.modules.sightings.models import Sighting

    data_in = {
        'encounters': [{}],
        'time': timestamp,
        'timeSpecificity': 'time',
        'locationId': test_utils.get_valid_location_id(),
    }
    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, data_in
    )

    sighting_id = uuids['sighting']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None

    sighting_utils.read_sighting(flask_app_client, admin_user, sighting_id)
    sighting_utils.delete_sighting(flask_app_client, admin_user, sighting_id)
