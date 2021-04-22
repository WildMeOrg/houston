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
    data_in = {'encounters': [{'taxonomy': {'id': '0000000'}}]}
    response = sighting_utils.create_sighting(
        flask_app_client, researcher_1, expected_status_code=400, data_in=data_in
    )
    assert response.json['errorFields'][0] == 'context'
    assert not response.json['success']

    # has encounters, but bunk assetReferences
    data_in = {
        'encounters': [{'assetReferences': [{'fail': 'fail'}]}],
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
    data_in['encounters'][0]['assetReferences'][0] = {
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
            }
        ],
    }
    response = sighting_utils.create_sighting(
        flask_app_client, researcher_1, expected_status_code=200, data_in=data_in
    )
    assert response.json['success']

    sighting_id = response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None

    response = sighting_utils.read_sighting(
        flask_app_client, researcher_1, sighting_id, expected_status_code=200
    )
    assert response.json['id'] == sighting_id

    # test some modification (should succeed)
    new_loc_id = 'test_2'
    response = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'replace', 'path': '/locationId', 'value': new_loc_id},
        ],
    )
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

    # upon success (yay) we clean up our mess
    sighting_utils.cleanup_tus_dir(transaction_id)
    sighting_utils.delete_sighting(flask_app_client, researcher_1, sighting_id)

    post_ct = test_utils.multi_count(db, (Sighting, Encounter, Asset, AssetGroup))
    assert orig_ct == post_ct


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
            }
        ],
    }
    response = sighting_utils.create_sighting(
        flask_app_client, None, expected_status_code=200, data_in=data_in
    )
    assert response.json['success']

    sighting_id = response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None

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
