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

    enc_1 = utils.generate_encounter_instance(
        user_email='mod1@user', user_password='mod1user', user_full_name='Test User'
    )
    enc_2 = utils.generate_encounter_instance(
        user_email='mod2@user', user_password='mod2user', user_full_name='Test User'
    )
    enc_3 = utils.generate_encounter_instance(
        user_email='mod3@user', user_password='mod3user', user_full_name='Test User'
    )

    owner_1 = utils.generate_user_instance(
        email='owner@localhost',
        is_researcher=True,
    )

    data_in = {
        'startTime': datetime.datetime.now().isoformat() + 'Z',
        'context': 'test',
        'locationId': 'test',
        'encounters': [
            {},
            {},
            {},
            {'locationId': 'Monster Island'},
        ],
    }
    response = sighting_utils.create_sighting(
        flask_app_client, researcher_1, expected_status_code=200, data_in=data_in
    )

    log.warning(
        '********** test_add_remove_encounters TEST RESPONSE: ' + str(response.json)
    )

    from app.modules.sightings.models import Sighting

    sighting_id = response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)

    assert response.json['success']
    result_data = response.json['result']

    from app.modules.encounters.models import Encounter

    enc_1.guid = result_data['encounters'][0]['id']
    enc_1.guid = result_data['encounters'][1]['id']
    enc_1.guid = result_data['encounters'][2]['id']
    # enc_1 = Encounter(
    #     guid=result_data['encounters'][0]['id'],
    #     version=result_data['encounters'][1].get('version', 2),
    #     owner_guid=researcher_1.guid,
    # )
    # enc_2 = Encounter(
    #     guid=result_data['encounters'][0]['id'],
    #     version=result_data['encounters'][1].get('version', 2),
    #     owner_guid=researcher_1.guid,
    # )
    # enc_3 = Encounter(
    #     guid=result_data['encounters'][0]['id'],
    #     version=result_data['encounters'][1].get('version', 2),
    #     owner_guid=researcher_1.guid,
    # )
    with db.session.begin():
        # db.session.add(individual_1)
        db.session.add(owner_1)
        # db.session.add(enc_1)
        # db.session.add(enc_2)
        # db.session.add(enc_3)

    sighting.add_encounter(enc_1)
    sighting.add_encounter(enc_2)
    sighting.add_encounter(enc_3)

    # You need to own an individual to modify it, and ownership is determined from it's encounters
    enc_1.owner = owner_1
    enc_2.owner = owner_1
    enc_3.owner = owner_1

    db.session.refresh(owner_1)

    response = individual_utils.create_individual(
        flask_app_client, owner_1, 200, {'encounters': [{'id': str(enc_1.guid)}]}
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
        '%s' % individual_1.guid,
        researcher_1,
        add_encounters,
        200,
    )

    assert str(enc_2.guid) in [
        str(encounter.guid) for encounter in individual_1.get_encounters()
    ]

    # remove the one we just verified was there
    remove_encounters = [
        utils.patch_remove_op('encounters', [str(enc_1.guid)]),
    ]

    individual_utils.patch_individual(
        flask_app_client,
        '%s' % individual_1.guid,
        researcher_1,
        remove_encounters,
        200,
    )

    assert str(enc_1.guid) not in [
        str(encounter.guid) for encounter in individual_1.get_encounters()
    ]

    # okay, now with multiple
    add_encounters = [
        utils.patch_add_op('encounters', [str(enc_1.guid), str(enc_3.guid)]),
    ]

    individual_utils.patch_individual(
        flask_app_client,
        '%s' % individual_1.guid,
        researcher_1,
        add_encounters,
        200,
    )

    assert str(enc_1.guid), str(enc_3.guid) in [
        str(encounter.guid) for encounter in individual_1.get_encounters()
    ]

    sighting.delete_cascade()
