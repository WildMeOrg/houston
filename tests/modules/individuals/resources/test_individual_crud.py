# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import logging

# import json
import uuid
import datetime
from app.modules.individuals.models import Individual

from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils

from tests import utils

log = logging.getLogger(__name__)


def test_get_individual_not_found(flask_app_client, researcher_1):
    response = individual_utils.read_individual(
        flask_app_client, researcher_1, uuid.uuid4, expected_status_code=404
    )
    assert response.status_code == 404


def test_create_read_delete_individual(db, flask_app_client):
    temp_owner = utils.generate_user_instance(
        email='owner@localhost',
        is_researcher=True,
    )
    temp_enc = utils.generate_encounter_instance(
        user_email='enc@user', user_password='encuser', user_full_name='enc user 1'
    )
    encounter_json = {'encounters': [{'id': str(temp_enc.guid)}]}
    temp_enc.owner = temp_owner
    response = individual_utils.create_individual(
        flask_app_client, temp_owner, expected_status_code=200, data_in=encounter_json
    )
    individual_guid = response.json['result']['id']

    assert individual_guid is not None

    read_individual = Individual.query.get(individual_guid)
    assert read_individual is not None

    individual_utils.delete_individual(flask_app_client, temp_owner, individual_guid)
    read_individual = Individual.query.get(individual_guid)
    assert read_individual is None

    response = individual_utils.read_individual(
        flask_app_client, temp_owner, individual_guid, expected_status_code=404
    )
    assert response.status_code == 404

    with db.session.begin():
        db.session.delete(temp_owner)
        db.session.delete(temp_enc)


def test_read_encounter_from_edm(db, flask_app_client):
    temp_owner = utils.generate_user_instance(
        email='owner@localhost',
        is_researcher=True,
    )
    temp_enc = utils.generate_encounter_instance(
        user_email='enc@user', user_password='encuser', user_full_name='enc user 1'
    )
    encounter_json = {'encounters': [{'id': str(temp_enc.guid)}]}
    temp_enc.owner = temp_owner
    response = individual_utils.create_individual(
        flask_app_client, temp_owner, expected_status_code=200, data_in=encounter_json
    )

    individual_guid = response.json['result']['id']

    read_response = individual_utils.read_individual(
        flask_app_client, temp_owner, individual_guid, expected_status_code=200
    )

    read_guid = read_response.json['result']['id']
    assert read_guid is not None

    read_individual = Individual.query.get(read_guid)

    assert read_individual is not None

    individual_utils.delete_individual(flask_app_client, temp_owner, individual_guid)
    read_individual = Individual.query.get(individual_guid)

    assert read_individual is None

    with db.session.begin():
        db.session.delete(temp_owner)
        db.session.delete(temp_enc)


def test_add_remove_encounters(db, flask_app_client, researcher_1):

    data_in = {
        'startTime': datetime.datetime.now().isoformat() + 'Z',
        'context': 'test',
        'locationId': 'test',
        'encounters': [
            {},
            {},
            {},
            {},
            {'locationId': 'Monster Island'},
        ],
    }

    response = sighting_utils.create_sighting(flask_app_client, researcher_1, data_in)

    from app.modules.sightings.models import Sighting

    sighting_id = response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)

    assert response.json['success']
    result_data = response.json['result']

    from app.modules.encounters.models import Encounter

    enc_1 = Encounter(
        guid=result_data['encounters'][0]['id'],
        owner_guid=researcher_1.guid,
    )

    enc_2 = Encounter(
        guid=result_data['encounters'][1]['id'],
        owner_guid=researcher_1.guid,
    )

    enc_3 = Encounter(
        guid=result_data['encounters'][2]['id'],
        owner_guid=researcher_1.guid,
    )

    enc_4 = Encounter(
        guid=result_data['encounters'][3]['id'],
        owner_guid=researcher_1.guid,
    )

    response = individual_utils.create_individual(
        flask_app_client, researcher_1, 200, {'encounters': [{'id': str(enc_1.guid)}]}
    )
    individual_1 = Individual.query.get(response.json['result']['id'])

    # # let's start with one
    # individual_1.add_encounter(enc_1)

    assert str(enc_1.guid) in [
        str(encounter.guid) for encounter in individual_1.get_encounters()
    ]

    add_encounters = [
        utils.patch_add_op('encounters', [str(enc_2.guid)]),
    ]

    individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        '%s' % individual_1.guid,
        patch_data=add_encounters,
        headers=None,
        expected_status_code=200,
    )

    assert str(enc_2.guid) in [
        str(encounter.guid) for encounter in individual_1.get_encounters()
    ]

    # remove the one we just verified was there
    remove_encounters = [
        utils.patch_remove_op('encounters', str(enc_1.guid)),
    ]

    individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        '%s' % individual_1.guid,
        remove_encounters,
        None,
        200,
    )

    assert str(enc_1.guid) not in [
        str(encounter.guid) for encounter in individual_1.get_encounters()
    ]

    # okay, now with multiple
    add_encounters = [
        utils.patch_add_op('encounters', [str(enc_3.guid), str(enc_4.guid)]),
    ]

    individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        '%s' % individual_1.guid,
        add_encounters,
        None,
        200,
    )

    assert str(enc_3.guid), str(enc_4.guid) in [
        str(encounter.guid) for encounter in individual_1.get_encounters()
    ]

    # removing all encounters will trigger delete cascade and clean up EDM
    # hack because sighting patch only takes one ID for remove. another PR for another day.
    enc_guids = [str(enc_2.guid), str(enc_3.guid), str(enc_4.guid)]

    for enc_guid in enc_guids:
        sighting_utils.patch_sighting(
            flask_app_client,
            researcher_1,
            sighting_id,
            patch_data=[
                {'op': 'remove', 'path': '/encounters', 'value': enc_guid},
            ],
            headers=(
                ('x-allow-delete-cascade-sighting', True),
                ('x-allow-delete-cascade-individual', True),
            ),
        )

    individual_1.delete()
    sighting.delete_cascade()
