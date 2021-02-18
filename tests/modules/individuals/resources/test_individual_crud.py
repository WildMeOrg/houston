# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from app.modules.individuals.models import Individual
import logging
import json

from tests.modules.individuals.resources import utils as individual_utils

from tests import utils

log = logging.getLogger(__name__)


def test_create_read_individual(flask_app_client, researcher_1, encounter_1):

    # TODO add checks for is_public
    encounter_1.owner = researcher_1
    response = individual_utils.create_individual(flask_app_client, researcher_1)

    individual_guid = response.json['guid']

    assert individual_guid is not None

    read_individual = Individual.query.get(individual_guid)
    read_individual.add_encounter(encounter_1)
    assert read_individual is not None

    response = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_guid
    )
    individual_guid = response.json['guid']
    read_individual = Individual.query.get(individual_guid)
    assert read_individual is not None


def test_read_failure_if_not_member_or_researcher(
    flask_app_client, regular_user, researcher_1
):
    # User without an encounter member or researcher privileges cannot access.
    # Worth considering. Since actual individual metadata is minimal and encounters
    # control their own data access, there is little risk in exposing individual to all logged in users.
    response = individual_utils.create_individual(flask_app_client, researcher_1)
    individual_guid = response.json['guid']
    response = individual_utils.read_individual(
        flask_app_client, regular_user, individual_guid, 403
    )
    assert 'guid' not in response.json.items()


def patch_individual(
    flask_app_client, individual_guid, user, data, expected_status_code=200
):
    with flask_app_client.login(user, auth_scopes=('individuals:write',)):
        response = flask_app_client.patch(
            '%s%s' % ('/api/v1/individuals/', individual_guid),
            content_type='application/json',
            data=json.dumps(data),
        )
    if expected_status_code == 200:
        utils.validate_dict_response(response, 200, {'guid'})
    else:
        utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def test_modify_encounter(db, flask_app_client, researcher_1, empty_individual):
    # pylint: disable=invalid-name
    # Had problems persisting and deleting fixture objects ¯\_(ツ)_/¯
    # EX: sqlalchemy.exc.InvalidRequestError: Instance '<Encounter at 0x7f72df5b2700>' has been deleted.
    mod_enc_1 = utils.generate_encounter_instance(
        user_email='mod1@user', user_password='mod1user', user_full_name='Test User'
    )
    mod_enc_2 = utils.generate_encounter_instance(
        user_email='mod2@user', user_password='mod2user', user_full_name='Test User'
    )

    with db.session.begin():
        db.session.add(empty_individual)
        db.session.add(mod_enc_1)
        db.session.add(mod_enc_2)

    encounters = [str(mod_enc_1.guid), str(mod_enc_2.guid)]

    replace_encounters = [
        utils.patch_replace_op('encounters', encounters),
    ]

    patch_individual(
        flask_app_client,
        '%s' % empty_individual.guid,
        researcher_1,
        replace_encounters,
        200,
    )
    with db.session.begin():
        db.session.refresh(empty_individual)
        db.session.refresh(mod_enc_1)
        db.session.refresh(mod_enc_2)

    assert encounters[0] in [
        str(encounter.guid) for encounter in empty_individual.get_encounters()
    ]
    assert encounters[1] in [
        str(encounter.guid) for encounter in empty_individual.get_encounters()
    ]

    with db.session.begin():
        db.session.delete(empty_individual)
        db.session.delete(mod_enc_1)
        db.session.delete(mod_enc_2)
