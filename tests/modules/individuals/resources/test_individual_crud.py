# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import logging

# import json
from app.modules.individuals.models import Individual

from tests.modules.individuals.resources import utils as individual_utils

from tests import utils

log = logging.getLogger(__name__)


def test_get_individual_not_found(flask_app_client):
    response = flask_app_client.get('/api/v1/individuals/wrong-uuid')
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

    with db.session.begin():
        db.session.delete(temp_owner)
        db.session.delete(temp_enc)


# def test_read_encounter_from_edm(db, flask_app_client):
#     temp_owner = utils.generate_user_instance(
#         email='owner@localhost',
#         is_researcher=True,
#     )
#     temp_enc = utils.generate_encounter_instance(
#         user_email='enc@user', user_password='encuser', user_full_name='enc user 1'
#     )
#     encounter_json = {'encounters': [{'id': str(temp_enc.guid)}]}
#     temp_enc.owner = temp_owner
#     response = individual_utils.create_individual(
#         flask_app_client, temp_owner, expected_status_code=200, data_in=encounter_json
#     )
#
#
#     individual_guid = response.json['result']['id']
#
#     read_response = individual_utils.read_individual(
#         flask_app_client, temp_owner, individual_guid, expected_status_code=200
#     )
#     log.warning("READ INDIVIDUAL : "+json.dumps(read_response.json))

#     read_guid = read_response.json['result']['id']
#     assert read_guid is not None
#
#     read_individual = Individual.query.get(read_guid)
#
#     assert read_individual is not None
#
#     individual_utils.delete_individual(flask_app_client, temp_owner, individual_guid)
#     read_individual = Individual.query.get(individual_guid)
#
#     assert read_individual is None
#
#     with db.session.begin():
#         db.session.delete(temp_owner)
#         db.session.delete(temp_enc)


def test_modify_encounters(db, flask_app_client, researcher_1, empty_individual):

    mod_enc_1 = utils.generate_encounter_instance(
        user_email='mod1@user', user_password='mod1user', user_full_name='Test User'
    )
    mod_enc_2 = utils.generate_encounter_instance(
        user_email='mod2@user', user_password='mod2user', user_full_name='Test User'
    )

    # You need to own an individual to modify it, and ownership is determined from it's encounters
    mod_enc_1.owner = researcher_1
    mod_enc_2.owner = researcher_1
    empty_individual.add_encounter(mod_enc_1)

    with db.session.begin():
        db.session.add(empty_individual)
        db.session.add(mod_enc_1)
        db.session.add(mod_enc_2)

    assert str(mod_enc_1.guid) in [
        str(encounter.guid) for encounter in empty_individual.get_encounters()
    ]

    replace_encounters = [
        utils.patch_replace_op('encounters', [str(mod_enc_2.guid)]),
    ]

    individual_utils.patch_individual(
        flask_app_client,
        '%s' % empty_individual.guid,
        researcher_1,
        replace_encounters,
        200,
    )

    with db.session.begin():
        db.session.refresh(empty_individual)

    assert str(mod_enc_2.guid) in [
        str(encounter.guid) for encounter in empty_individual.get_encounters()
    ]

    # restore to original state with no encounters
    # (although we need this to fail in the near future when the constraint is added to require >0 encounters!)
    replace_encounters = [
        utils.patch_replace_op('encounters', []),
    ]

    individual_utils.patch_individual(
        flask_app_client,
        '%s' % empty_individual.guid,
        researcher_1,
        replace_encounters,
        200,
    )

    with db.session.begin():
        db.session.delete(mod_enc_1)
        db.session.delete(mod_enc_2)
