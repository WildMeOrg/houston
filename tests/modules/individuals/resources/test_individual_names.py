# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils

from app.modules.encounters.models import Encounter
from app.modules.sightings.models import Sighting


def test_get_set_individual_names(db, flask_app_client, researcher_1):

    data_in = {
        'encounters': [{}],
        'startTime': '2000-01-01T01:01:01Z',
        'locationId': 'test',
    }

    try:

        response = sighting_utils.create_sighting(
            flask_app_client, researcher_1, data_in=data_in
        )

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
            'names': {
                'defaultName': 'Godzilla',
                'nickname': 'Doctor Atomic',
                'oldName': 'critter-271',
            },
            'encounters': [{'id': str(enc.guid)}],
        }

        individual_response = individual_utils.create_individual(
            flask_app_client, researcher_1, 200, individual_data_in
        )

        assert individual_response.json['result']['id'] is not None

        individual_id = individual_response.json['result']['id']

        individual_json = individual_utils.read_individual(
            flask_app_client, researcher_1, individual_id
        ).json

        assert individual_json['result']['names']['defaultName'] == 'Godzilla'
        assert individual_json['result']['names']['nickname'] == 'Doctor Atomic'
        assert individual_json['result']['names']['oldName'] == 'critter-271'

        # change one
        patch_data = [
            utils.patch_replace_op('names', "{'nickname': 'Todd' }"),
        ]
        patch_individual_response = individual_utils.patch_individual(
            flask_app_client, researcher_1, individual_id, patch_data
        )

        assert patch_individual_response.json['guid'] is not None

        individual_json = individual_utils.read_individual(
            flask_app_client, researcher_1, patch_individual_response.json['guid']
        ).json

        assert individual_json['result']['id'] is not None
        assert individual_json['result']['names']['nickname'] == 'Todd'

        # add one
        patch_data = [
            utils.patch_replace_op('names', "{'newestName': 'Old Fancypants'}"),
        ]
        patch_individual_response = individual_utils.patch_individual(
            flask_app_client, researcher_1, individual_id, patch_data
        )

        assert patch_individual_response.json['guid'] is not None

        individual_json = individual_utils.read_individual(
            flask_app_client, researcher_1, patch_individual_response.json['guid']
        ).json

        assert individual_json['result']['id'] is not None
        assert individual_json['result']['names']['nickname'] == 'Todd'

        # remove one
        patch_data = [
            utils.patch_remove_op('names', "{'oldName': 'critter-271' }"),
        ]
        patch_individual_response = individual_utils.patch_individual(
            flask_app_client, researcher_1, individual_id, patch_data
        )

        assert patch_individual_response.json['guid'] is not None

        individual_json = individual_utils.read_individual(
            flask_app_client, researcher_1, patch_individual_response.json['guid']
        ).json

        assert individual_json['result']['id'] is not None
        assert 'oldName' not in individual_json['result']['names']

    finally:
        individual_utils.delete_individual(
            flask_app_client, researcher_1, individual_response.json['result']['id']
        )
        sighting.delete_cascade()
        enc.delete_cascade()


def test_ensure_default_name_on_individual_creation(db, flask_app_client, researcher_1):

    data_in = {
        'encounters': [{}],
        'startTime': '2000-01-01T01:01:01Z',
        'locationId': 'test',
    }

    try:
        response = sighting_utils.create_sighting(
            flask_app_client, researcher_1, data_in=data_in
        )

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

        # without an explicit default name defined, the name provided should also become the default
        only_name = 'Uncle Pumpkin'

        individual_data_in = {
            'names': {'nickname': only_name},
            'encounters': [{'id': str(enc.guid)}],
        }

        individual_response = individual_utils.create_individual(
            flask_app_client, researcher_1, 200, individual_data_in
        )

        assert individual_response.json['result']['id'] is not None

        individual_id = individual_response.json['result']['id']

        individual_json = individual_utils.read_individual(
            flask_app_client, researcher_1, individual_id
        ).json

        assert individual_json['result']['names']['defaultName'] == only_name
        assert individual_json['result']['names']['nickname'] == only_name

    finally:
        individual_utils.delete_individual(
            flask_app_client, researcher_1, individual_response.json['result']['id']
        )
        sighting.delete_cascade()
        enc.delete_cascade()
