# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import logging

from tests.modules.individuals.resources import utils as utils

log = logging.getLogger(__name__)

from app.modules.individuals.models import Individual


def test_create_read_individual(flask_app_client, researcher_1, encounter_1):

    # TODO add checks for is_public
    encounter_1.owner = researcher_1
    response = utils.create_individual(flask_app_client, researcher_1)

    individual_guid = response.json['guid']

    assert individual_guid is not None

    read_individual = Individual.query.get(individual_guid)
    read_individual.add_encounter(encounter_1)
    assert read_individual is not None

    response = utils.read_individual(flask_app_client, researcher_1, individual_guid)
    individual_guid = response.json['guid']
    read_individual = Individual.query.get(individual_guid)
    assert read_individual is not None


def test_read_failure_if_not_member_or_researcher(
    flask_app_client, regular_user, researcher_1
):
    # User without an encounter member or researcher privileges cannot access.
    # Worth considering. Since actual individual metadata is minimal and encounters
    # control their own data access, there is little risk in exposing individual to all logged in users.
    response = utils.create_individual(flask_app_client, researcher_1)
    individual_guid = response.json['guid']
    response = utils.read_individual(flask_app_client, regular_user, individual_guid, 403)
    assert 'guid' not in response.json.items()
