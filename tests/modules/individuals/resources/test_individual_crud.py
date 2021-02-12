# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.individuals.resources import utils as utils

import logging

log = logging.getLogger(__name__)


def test_create_and_delete_individual(flask_app_client, admin_user):
    from app.modules.individuals.models import Individual

    response = utils.create_individual(flask_app_client, admin_user)

    individual_guid = response.json['guid']

    assert individual_guid is not None

    read_individual = Individual.query.get(individual_guid)
    assert read_individual is not None

    utils.read_individual(flask_app_client, admin_user, individual_guid)
    utils.delete_individual(flask_app_client, admin_user, individual_guid)

    read_individual = Individual.query.get(individual_guid)
    assert read_individual is None
