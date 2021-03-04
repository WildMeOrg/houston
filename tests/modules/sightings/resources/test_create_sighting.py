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


def test_create_and_delete_sighting(db, flask_app_client, researcher_1):
    # from flask import current_app
    from app.modules.sightings.models import Sighting
    from app.modules.encounters.models import Encounter
    import datetime

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
    encounter_id = response.json['result']['encounters'][0]['id']

    # until DELETE api is completed, this is our cleanup  FIXME
    encounter = Encounter.query.get(encounter_id)
    # encounter.delete_from_edm(current_app)
    encounter.delete()

    sighting = Sighting.query.get(sighting_id)
    # sighting.delete_from_edm(current_app)  # TODO not yet implemented!
    sighting.delete()
