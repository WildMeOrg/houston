# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
import pytest
import json

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge(db, flask_app_client, researcher_1):

    from app.modules.encounters.models import Encounter
    from app.modules.sightings.models import Sighting

    sighting_data_in = {
        'encounters': [
            {
                'decimalLatitude': 45.999,
                'decimalLongitude': 45.999,
                'verbatimLocality': 'Town Square',
                'locationId': 'Legoland',
            }
        ],
        'startTime': '2000-01-01T01:01:01Z',
        'locationId': 'test',
    }
    individual_data_in = {
        'names': {'defaultName': 'Godzilla'},
        'sex': 'female',
        'comments': 'Test Individual',
        'timeOfBirth': '872846040000',
    }

    try:

        res_sighting, res_individual = sighting_utils.create_sighting_and_individual(
            flask_app_client, researcher_1, sighting_data_in, individual_data_in
        )
        json_sighting1 = res_sighting.json['result']
        json_individual1 = res_individual.json['result']
        assert (
            json_sighting1['encounters'][0]['id']
            == json_individual1['encounters'][0]['id']
        )

        individual_data_in['names']['defaultName'] = 'Mothra'
        sighting_data_in['locationId'] = 'test2'
        res_sighting, res_individual = sighting_utils.create_sighting_and_individual(
            flask_app_client, researcher_1, sighting_data_in, individual_data_in
        )
        json_sighting2 = res_sighting.json['result']
        json_individual2 = res_individual.json['result']
        assert (
            json_sighting2['encounters'][0]['id']
            == json_individual2['encounters'][0]['id']
        )

        sighting1 = Sighting.query.get(json_sighting1['id'])
        assert sighting1 is not None
        sighting2 = Sighting.query.get(json_sighting2['id'])
        assert sighting2 is not None
        encounter1 = Encounter.query.get(json_sighting1['encounters'][0]['id'])
        assert encounter1 is not None
        encounter2 = Encounter.query.get(json_sighting2['encounters'][0]['id'])
        assert encounter2 is not None

        data_in = {}  # first try with bunk data
        with flask_app_client.login(researcher_1, auth_scopes=('individuals:write',)):
            response = flask_app_client.post(
                f"/api/v1/individuals/{json_individual1['id']}/merge",
                data=json.dumps(data_in),
                content_type='application/json',
            )
        assert response.status_code == 500
        assert (
            'message' in response.json
            and 'list of individuals' in response.json['message']
        )

        # send an invalid guid
        bad_id = '00000000-0000-0000-0000-000000002170'
        data_in = [bad_id]
        with flask_app_client.login(researcher_1, auth_scopes=('individuals:write',)):
            response = flask_app_client.post(
                f"/api/v1/individuals/{json_individual1['id']}/merge",
                data=json.dumps(data_in),
                content_type='application/json',
            )
        assert response.status_code == 500
        assert (
            'message' in response.json
            and f'{bad_id} is invalid' in response.json['message']
        )

        # now with valid list of from-individuals
        data_in = {
            'fromIndividualIds': [json_individual2['id']],
        }
        # data_in = [json_individual2['id']]  # would also be valid
        with flask_app_client.login(researcher_1, auth_scopes=('individuals:write',)):
            response = flask_app_client.post(
                f"/api/v1/individuals/{json_individual1['id']}/merge",
                data=json.dumps(data_in),
                content_type='application/json',
            )
        assert response.status_code == 200
        assert False

    finally:
        individual_utils.delete_individual(
            flask_app_client, researcher_1, json_individual1['id']
        )
        individual_utils.delete_individual(
            flask_app_client, researcher_1, json_individual2['id']
        )
        sighting1.delete_cascade()
        sighting2.delete_cascade()
