# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils


def test_modify_individual_edm_fields(db, flask_app_client, researcher_1):

    from app.modules.encounters.models import Encounter
    from app.modules.sightings.models import Sighting

    data_in = {
        'encounters': [{}],
        'startTime': '2000-01-01T01:01:01Z',
        'locationId': 'test',
    }

    try:

        response = sighting_utils.create_sighting(flask_app_client, researcher_1, data_in)

        response_json = response.json

        assert response_json['result']['encounters']
        assert response_json['result']['encounters'][0]['id']

        guid = response_json['result']['encounters'][0]['id']
        enc = Encounter.query.get(guid)
        assert enc is not None

        with db.session.begin():
            db.session.add(enc)

        sighting_id = response_json['result']['id']
        sighting = Sighting.query.get(sighting_id)
        assert sighting is not None

        individual_data_in = {
            'names': {'defaultName': 'Godzilla'},
            'encounters': [{'id': str(enc.guid)}],
            'sex': 'female',
            'comments': 'Test Individual',
            'timeOfBirth': '872846040000',
        }

        individual_response = individual_utils.create_individual(
            flask_app_client, researcher_1, 200, individual_data_in
        )

        assert individual_response.json['result']['id'] is not None

        individual_id = individual_response.json['result']['id']

        individual_json = individual_utils.read_individual(
            flask_app_client, researcher_1, individual_id
        ).json

        assert individual_json['result']['sex'] == 'female'
        assert individual_json['result']['names']['defaultName'] == 'Godzilla'
        assert individual_json['result']['comments'] == 'Test Individual'

        # when skynet went online
        assert individual_json['result']['timeOfBirth'] == '872846040000'

        patch_op_sex = [
            utils.patch_replace_op('sex', 'male'),
        ]

        patch_individual_response = individual_utils.patch_individual(
            flask_app_client, researcher_1, individual_id, patch_op_sex
        )

        # back to the future 2 date
        patch_data = [
            utils.patch_replace_op('timeOfBirth', '1445410800000'),
        ]

        patch_individual_response = individual_utils.patch_individual(
            flask_app_client, researcher_1, individual_id, patch_data
        )

        assert patch_individual_response.json['guid'] is not None

        individual_json = individual_utils.read_individual(
            flask_app_client, researcher_1, patch_individual_response.json['guid']
        ).json

        assert individual_json['result']['id'] is not None
        assert individual_json['result']['sex'] == 'male'
        assert individual_json['result']['timeOfBirth'] == '1445410800000'

    finally:
        individual_utils.delete_individual(
            flask_app_client, researcher_1, individual_response.json['result']['id']
        )
        sighting.delete_cascade()
        enc.delete_cascade()
