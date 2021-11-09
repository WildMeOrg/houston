# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.sightings.resources import utils as sighting_utils

increment = 0


def simple_sighting_encounter(db, flask_app_client, user, individual_sex='female'):
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
