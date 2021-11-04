# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
import pytest
import json

from tests.utils import module_unavailable

increment = 0


def prep_data(db, flask_app_client, user, individual_sex='female'):
    from app.modules.encounters.models import Encounter
    from app.modules.sightings.models import Sighting

    global increment
    sighting_data_in = {
        'encounters': [
            {
                'decimalLatitude': 45.999,
                'decimalLongitude': 45.999,
                'verbatimLocality': 'Legoland Town Square',
                'locationId': f'Location {increment}',
            }
        ],
        'startTime': '2000-01-01T01:01:01Z',
        'locationId': f'test-{increment}',
    }
    individual_data_in = {
        'names': {'defaultName': f'NAME {increment}'},
        'sex': individual_sex,
        'comments': 'Test Individual',
        'timeOfBirth': '872846040000',
    }
    increment += 1
    res_sighting, res_individual = sighting_utils.create_sighting_and_individual(
        flask_app_client, user, sighting_data_in, individual_data_in
    )
    json_sighting = res_sighting.json['result']
    json_individual = res_individual.json['result']
    assert json_sighting['encounters'][0]['id'] == json_individual['encounters'][0]['id']
    encounter = Encounter.query.get(json_sighting['encounters'][0]['id'])
    assert encounter is not None
    sighting = Sighting.query.get(json_sighting['id'])
    assert sighting is not None
    return sighting, encounter


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge_basics(db, flask_app_client, researcher_1):

    individual1_id = None
    sighting1 = None
    encounter1 = None
    individual2_id = None
    sighting2 = None
    encounter2 = None
    try:
        sighting1, encounter1 = prep_data(db, flask_app_client, researcher_1)
        individual1_id = str(encounter1.individual_guid)
        sighting2, encounter2 = prep_data(db, flask_app_client, researcher_1)
        individual2_id = str(encounter2.individual_guid)

        data_in = {}  # first try with bunk data
        with flask_app_client.login(researcher_1, auth_scopes=('individuals:write',)):
            response = flask_app_client.post(
                f'/api/v1/individuals/{individual1_id}/merge',
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
                f'/api/v1/individuals/{individual1_id}/merge',
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
            'fromIndividualIds': [individual2_id],
        }
        # data_in = [individual2_id]  # would also be valid
        # note: this tests positive permission case as well (user owns everything)
        with flask_app_client.login(researcher_1, auth_scopes=('individuals:write',)):
            response = flask_app_client.post(
                f'/api/v1/individuals/{individual1_id}/merge',
                data=json.dumps(data_in),
                content_type='application/json',
            )
        assert response.status_code == 200
        assert False

    finally:
        individual_utils.delete_individual(flask_app_client, researcher_1, individual1_id)
        individual_utils.delete_individual(flask_app_client, researcher_1, individual2_id)
        sighting1.delete_cascade()
        sighting2.delete_cascade()


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge_permissions(db, flask_app_client, researcher_1, researcher_2):

    individual1_id = None
    sighting1 = None
    encounter1 = None
    individual2_id = None
    sighting2 = None
    encounter2 = None
    try:
        sighting1, encounter1 = prep_data(db, flask_app_client, researcher_1)
        individual1_id = str(encounter1.individual_guid)
        sighting2, encounter2 = prep_data(db, flask_app_client, researcher_1)
        individual2_id = str(encounter2.individual_guid)

        # this tests as researcher_2, which should trigger a merge-request
        # NOTE: merge_request not yet implmented, so fails accordingly
        data_in = [individual2_id]
        with flask_app_client.login(researcher_2, auth_scopes=('individuals:write',)):
            response = flask_app_client.post(
                f'/api/v1/individuals/{individual1_id}/merge',
                data=json.dumps(data_in),
                content_type='application/json',
            )
        assert response.status_code == 500
        assert response.json['merge_request']
        assert response.json['message'] == 'Merge failed'
        assert set(response.json['blocking_encounters']) == set(
            [str(encounter1.guid), str(encounter2.guid)]
        )

        # permission where user owns just one encounter
        sighting3, encounter3 = prep_data(db, flask_app_client, researcher_2)
        individual3_id = str(encounter3.individual_guid)

        data_in = [individual3_id]
        with flask_app_client.login(researcher_2, auth_scopes=('individuals:write',)):
            response = flask_app_client.post(
                f'/api/v1/individuals/{individual1_id}/merge',
                data=json.dumps(data_in),
                content_type='application/json',
            )
        assert response.status_code == 500
        assert response.json['merge_request']
        assert response.json['message'] == 'Merge failed'
        assert response.json['blocking_encounters'] == [str(encounter1.guid)]

    finally:
        individual_utils.delete_individual(flask_app_client, researcher_1, individual1_id)
        individual_utils.delete_individual(flask_app_client, researcher_1, individual2_id)
        individual_utils.delete_individual(flask_app_client, researcher_2, individual3_id)
        sighting1.delete_cascade()
        sighting2.delete_cascade()
        sighting3.delete_cascade()
