# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import sqlalchemy

import logging

from app.modules.individuals.models import Individual
from app.modules.relationships.models import Relationship

from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.encounters.resources import utils as encounter_utils
from tests.modules.relationships.resources import utils as relationship_utils
from tests import utils
from tests.utils import module_unavailable
import pytest

log = logging.getLogger(__name__)


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
@pytest.mark.skipif(
    module_unavailable('relationships'), reason='Relationships module disabled'
)
def test_create_read_delete_relationship(flask_app_client, researcher_1):

    temp_owner = None
    temp_enc_1 = None
    temp_enc_2 = None
    individual_1_guid = None
    individual_2_guid = None

    # try:
    temp_owner = utils.generate_user_instance(
        email='owner@localhost',
        is_researcher=True,
    )

    temp_enc_1 = encounter_utils.create_encounter(flask_app_client, researcher_1)
    temp_enc_1_guid = temp_enc_1.json['result']['encounters'][0]['id']

    enc_1_json = {'encounters': [{'id': str(temp_enc_1_guid)}]}
    temp_enc_1.owner = researcher_1
    response = individual_utils.create_individual(
        flask_app_client, researcher_1, expected_status_code=200, data_in=enc_1_json
    )
    individual_1_guid = response.json['result']['id']

    temp_enc_2 = encounter_utils.create_encounter(flask_app_client, researcher_1)
    temp_enc_2_guid = temp_enc_2.json['result']['encounters'][0]['id']

    enc_2_json = {'encounters': [{'id': str(temp_enc_2_guid)}]}
    temp_enc_2.owner = researcher_1
    response = individual_utils.create_individual(
        flask_app_client, researcher_1, expected_status_code=200, data_in=enc_2_json
    )
    individual_2_guid = response.json['result']['id']

    relationship_json = {
        'individual_1_guid': individual_1_guid,
        'individual_2_guid': individual_2_guid,
        'individual_1_role': 'Mother',
        'individual_2_role': 'Calf',
    }
    response = relationship_utils.create_relationship(
        flask_app_client,
        researcher_1,
        expected_status_code=200,
        data_in=relationship_json,
    )

    log.debug(
        '+++++++++++++++++++++++ RELATIONSHIP RESPONSE OUTSIDE UTIL: '
        + str(response.json)
    )

    relationship_guid = response.json['guid']

    # finally:
    resp = individual_utils.delete_individual(
        flask_app_client, researcher_1, individual_1_guid
    )
    log.debug('INDIVIDUAL DELETION RESP 2: ' + str(resp.json))
    resp = individual_utils.delete_individual(
        flask_app_client, researcher_1, individual_2_guid
    )
    log.debug('INDIVIDUAL DELETION RESP 3: ' + str(resp.json))
    relationship_utils.delete_relationship(
        flask_app_client, researcher_1, relationship_guid
    )
