# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.sightings.resources import utils as sighting_utils


def test_create_failures(flask_app_client, researcher_1):
    transaction_id, test_filename = sighting_utils.prep_tus_dir()

    # default data_in will fail (no encounters)
    response = sighting_utils.create_sighting(
        flask_app_client, researcher_1, expected_status_code=400
    )
    assert response.json['passed_message'] == 'Must have at least one encounter'
    assert not response.json['success']

    # has encounters, zero assetReferences, but fails on bad taxonomy
    data_in = {'encounters': [{'taxonomy': {'id': '0000000'}}]}
    response = sighting_utils.create_sighting(
        flask_app_client, researcher_1, expected_status_code=400, data_in=data_in
    )
    assert 'invalid taxonomy' in response.json['passed_message']['details']
    assert not response.json['success']

    # has encounters, but bunk assetReferences
    data_in = {'encounters': [{'assetReferences': [{'fail': 'fail'}]}]}
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


def test_create_and_delete_sighting(db, flask_app_client, researcher_1, staff_user):
    from app.modules.sightings.models import Sighting
    from app.modules.encounters.models import Encounter
    from app.modules.assets.models import Asset
    from app.modules.submissions.models import Submission
    import datetime

    # we should end up with these same counts (which _should be_ all zeros!)
    orig_ct = [
        sighting_utils.row_count(db, Sighting),
        sighting_utils.row_count(db, Encounter),
        sighting_utils.row_count(db, Asset),
        sighting_utils.row_count(db, Submission),
    ]

    timestamp = datetime.datetime.now().isoformat()
    transaction_id, test_filename = sighting_utils.prep_tus_dir()
    data_in = {
        'startTime': timestamp,
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

    # upon success (yay) we clean up our mess
    sighting_utils.cleanup_tus_dir(transaction_id)
    sighting_utils.delete_sighting(flask_app_client, staff_user, sighting_id)

    post_ct = [
        sighting_utils.row_count(db, Sighting),
        sighting_utils.row_count(db, Encounter),
        sighting_utils.row_count(db, Asset),
        sighting_utils.row_count(db, Submission),
    ]
    assert orig_ct == post_ct
