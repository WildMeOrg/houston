# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.sightings.resources import utils as sighting_utils
from tests import utils as test_utils


def test_get_sighting_not_found(flask_app_client):
    response = flask_app_client.get('/api/v1/sightings/wrong-uuid')
    assert response.status_code == 404


def test_create_failures(flask_app_client, test_root, researcher_1):
    transaction_id, test_filename = sighting_utils.prep_tus_dir(test_root)

    # default data_in will fail (no encounters)
    response = sighting_utils.create_sighting(
        flask_app_client, researcher_1, expected_status_code=400
    )
    assert response.json['passed_message'] == 'Must have at least one encounter'
    assert not response.json['success']

    # has encounters, zero assetReferences, but fails on bad (missing) context value
    data_in = {'encounters': [{}]}
    response = sighting_utils.create_sighting(
        flask_app_client, researcher_1, expected_status_code=400, data_in=data_in
    )
    assert response.json['errorFields'][0] == 'context'
    assert not response.json['success']

    # has encounters, but bunk assetReferences
    data_in = {
        'encounters': [{}],
        'assetReferences': [{'fail': 'fail'}],
        'context': 'test',
        'locationId': 'test',
    }
    response = sighting_utils.create_sighting(
        flask_app_client, researcher_1, expected_status_code=400, data_in=data_in
    )
    assert (
        response.json['passed_message'] == 'Invalid assetReference data in encounter(s)'
    )
    assert not response.json['success']

    # assetReferences, but no files for them
    data_in['assetReferences'][0] = {
        'transactionId': transaction_id,
        'path': 'i-dont-exist.jpg',
    }
    response = sighting_utils.create_sighting(
        flask_app_client, researcher_1, expected_status_code=400, data_in=data_in
    )
    assert (
        response.json['passed_message'] == 'Invalid assetReference data in encounter(s)'
    )
    assert not response.json['success']
    sighting_utils.cleanup_tus_dir(transaction_id)


def test_create_and_modify_and_delete_sighting(
    db, flask_app_client, researcher_1, test_root, staff_user
):
    from app.modules.sightings.models import Sighting
    from app.modules.encounters.models import Encounter
    from app.modules.assets.models import Asset
    from app.modules.asset_groups.models import AssetGroup
    import datetime

    # we should end up with these same counts (which _should be_ all zeros!)
    orig_ct = test_utils.multi_count(db, (Sighting, Encounter, Asset, AssetGroup))

    timestamp = datetime.datetime.now().isoformat()
    transaction_id, test_filename = sighting_utils.prep_tus_dir(test_root)
    data_in = {
        'startTime': timestamp,
        'context': 'test',
        'locationId': 'test',
        'encounters': [
            {
                'assetReferences': [
                    {
                        'transactionId': transaction_id,
                        'path': test_filename,
                    }
                ]
            },
            {'locationId': 'test2'},
        ],
    }
    response = sighting_utils.create_sighting(
        flask_app_client, researcher_1, expected_status_code=200, data_in=data_in
    )
    assert response.json['success']

    sighting_id = response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None

    enc0_id = response.json['result']['encounters'][0]['id']
    enc1_id = response.json['result']['encounters'][1]['id']
    assert enc0_id is not None
    assert enc1_id is not None

    response = sighting_utils.read_sighting(
        flask_app_client, researcher_1, sighting_id, expected_status_code=200
    )
    assert response.json['id'] == sighting_id

    # test to see if we grew by 1 sighting and 2 encounters
    ct = test_utils.multi_count(db, (Sighting, Encounter, Asset, AssetGroup))
    assert ct[0] == orig_ct[0] + 1
    assert ct[1] == orig_ct[1] + 2

    # test some simple modification (should succeed)
    new_loc_id = 'test_2'
    response = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'replace', 'path': '/locationId', 'value': new_loc_id},
        ],
    )
    assert response.json['success']
    # check that change was made
    response = sighting_utils.read_sighting(
        flask_app_client, researcher_1, sighting_id, expected_status_code=200
    )
    assert response.json['id'] == sighting_id
    assert response.json['locationId'] == new_loc_id

    # test some modification (should fail due to invalid data)
    response = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'add', 'path': '/decimalLatitude', 'value': 999.9},
        ],
        expected_status_code=400,
    )

    # more complex patch: we op=remove the first encounter; should succeed no problem cuz there is one enc remaining
    response = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'remove', 'path': '/encounters', 'value': enc0_id},
        ],
    )
    # test to see if we now are -1 encounter
    ct = test_utils.multi_count(db, (Sighting, Encounter, Asset, AssetGroup))
    assert ct[1] == orig_ct[1] + 1  # previously was + 2

    # similar to above, but this should fail as this is our final encounter, and thus cascade-deletes the occurrence -- and this
    #   requires confirmation
    response = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'remove', 'path': '/encounters', 'value': enc1_id},
        ],
        expected_status_code=400,
    )
    assert response.json['edm_status_code'] == 602
    # should still have same number encounters as above here
    ct = test_utils.multi_count(db, (Sighting, Encounter, Asset, AssetGroup))
    assert ct[1] == orig_ct[1] + 1

    # now we try again, but this time with header to allow for cascade deletion of sighting
    response = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'remove', 'path': '/encounters', 'value': enc1_id},
        ],
        headers=(('x-allow-delete-cascade-sighting', True),),
    )
    # now this should bring us back to where we started
    ct = test_utils.multi_count(db, (Sighting, Encounter, Asset, AssetGroup))
    assert ct == orig_ct

    # upon success (yay) we clean up our mess
    sighting_utils.cleanup_tus_dir(transaction_id)
    # no longer need to utils.delete_sighting() cuz cascade killed it above


def test_create_anon_and_delete_sighting(db, flask_app_client, staff_user, test_root):
    from app.modules.sightings.models import Sighting
    from app.modules.encounters.models import Encounter
    from app.modules.assets.models import Asset
    from app.modules.users.models import User
    from app.modules.asset_groups.models import AssetGroup
    import datetime

    # we should end up with these same counts (which _should be_ all zeros!)
    orig_ct = test_utils.multi_count(db, (Sighting, Encounter, Asset, AssetGroup))

    timestamp = datetime.datetime.now().isoformat()
    transaction_id, test_filename = sighting_utils.prep_tus_dir(test_root)
    sighting_utils.prep_tus_dir(test_root, filename='fluke.jpg')
    data_in = {
        'startTime': timestamp,
        'context': 'test',
        'locationId': 'test',
        'encounters': [{}],
        'assetReferences': [
            {
                'transactionId': transaction_id,
                'path': test_filename,
            },
            {
                'transactionId': transaction_id,
                'path': 'fluke.jpg',
            },
        ],
    }
    response = sighting_utils.create_sighting(
        flask_app_client, None, expected_status_code=200, data_in=data_in
    )
    assert response.json['success']
    assets = sorted(response.json['result']['assets'], key=lambda a: a['filename'])
    asset_guids = [a['guid'] for a in assets]
    assert assets == [
        {
            'filename': 'fluke.jpg',
            'guid': asset_guids[0],
            'src': f'/api/v1/assets/src/{asset_guids[0]}',
        },
        {
            'filename': 'zebra.jpg',
            'guid': asset_guids[1],
            'src': f'/api/v1/assets/src/{asset_guids[1]}',
        },
    ]

    # Check sighting and assets are stored in the database
    sighting_id = response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None
    asset_guids.sort()
    assert sorted([str(a.asset_guid) for a in sighting.assets]) == asset_guids

    # Check assets are returned in GET sighting
    with flask_app_client.login(staff_user, auth_scopes=('sightings:read',)):
        response = flask_app_client.get(f'/api/v1/sightings/{sighting_id}')
        assert sorted([a['guid'] for a in response.json['assets']]) == asset_guids

    # test some modification; this should fail (401) cuz anon should not be allowed
    new_loc_id = 'test_2_fail'
    response = sighting_utils.patch_sighting(
        flask_app_client,
        None,
        sighting_id,
        patch_data=[
            {'op': 'replace', 'path': '/locationId', 'value': new_loc_id},
        ],
        expected_status_code=401,
    )

    # upon success (yay) we clean up our mess (but need staff_user to do it)
    sighting_utils.cleanup_tus_dir(transaction_id)
    sighting_utils.delete_sighting(flask_app_client, staff_user, sighting_id)

    # anonymous, but using valid (active) user - should be blocked with 403
    data_in = {
        'startTime': timestamp,
        'context': 'test',
        'locationId': 'test',
        'submitterEmail': 'public@localhost',
        'encounters': [{}],
    }
    response = sighting_utils.create_sighting(
        flask_app_client, None, expected_status_code=403, data_in=data_in
    )

    # anonymous, but using acceptable email address (should create new inactive user)
    test_email = 'test_anon_123@example.com'
    data_in = {
        'startTime': timestamp,
        'context': 'test',
        'locationId': 'test',
        'submitterEmail': test_email,
        'encounters': [{}],
    }
    response = sighting_utils.create_sighting(
        flask_app_client, None, expected_status_code=200, data_in=data_in
    )
    sighting_id = response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None
    new_user = User.find(email=test_email)
    assert new_user is not None
    assert sighting.encounters[0].submitter == new_user

    # upon success (yay) we clean up our mess (but need staff_user to do it)
    sighting_utils.cleanup_tus_dir(transaction_id)
    sighting_utils.delete_sighting(flask_app_client, staff_user, sighting_id)
    new_user.delete()

    post_ct = test_utils.multi_count(db, (Sighting, Encounter, Asset, AssetGroup))
    assert orig_ct == post_ct
