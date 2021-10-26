# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge(db, flask_app_client, researcher_1):

    from app.modules.encounters.models import Encounter
    from app.modules.sightings.models import Sighting
    from app.modules.individuals.models import Individual

    data_in = {
        'encounters': [
            {
                'locationId': 'one',
            },
            {
                'locationId': 'two',
            },
        ],
        'startTime': '2000-01-01T01:01:01Z',
        'locationId': 'test',
    }

    response = sighting_utils.create_sighting(flask_app_client, researcher_1, data_in)
    enc1_guid = response.json['result']['encounters'][0]['id']
    enc2_guid = response.json['result']['encounters'][1]['id']
    enc1 = Encounter.query.get(enc1_guid)
    enc2 = Encounter.query.get(enc1_guid)
    sighting = Sighting.query.get(response.json['result']['id'])

    # with db.session.begin():
    # db.session.add(enc)

    individual_data_in = {
        'names': {'defaultName': 'NAME1'},
        'encounters': [
            {
                'id': enc1_guid,
            }
        ],
        'sex': 'female',
    }
    individual_response = individual_utils.create_individual(
        flask_app_client, researcher_1, 200, individual_data_in
    )
    indiv1_guid = individual_response.json['result']['id']

    # now same for 2nd indiv
    individual_data_in['names']['defaultName'] = 'NAME2'
    individual_data_in['encounters'][0]['id'] = enc2_guid
    # both will be set female
    individual_response = individual_utils.create_individual(
        flask_app_client, researcher_1, 200, individual_data_in
    )
    indiv2_guid = individual_response.json['result']['id']

    indiv1 = Individual.query.get(indiv1_guid)
    indiv2 = Individual.query.get(indiv2_guid)
    assert indiv1 is not None
    assert indiv2 is not None
    assert str(indiv1.encounters[0].guid) == enc1_guid
    assert str(indiv2.encounters[0].guid) == enc2_guid

    try:
        indiv1.merge_from()  # fail cuz no source-individuals
    except ValueError as ve:
        assert 'at least 2' in str(ve)

    # saving for patch

    # patch_op_sex = [
    # utils.patch_replace_op('sex', 'male'),
    # ]

    # patch_individual_response = individual_utils.patch_individual(
    # flask_app_client, researcher_1, individual_id, patch_op_sex
    # )

    individual_utils.delete_individual(flask_app_client, researcher_1, indiv1.guid)
    individual_utils.delete_individual(flask_app_client, researcher_1, indiv2.guid)
    sighting.delete_cascade()
    enc1.delete_cascade()
    enc2.delete_cascade()
