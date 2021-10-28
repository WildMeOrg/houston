# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import sqlalchemy

import logging

from app.modules.individuals.models import Individual
from app.modules.relationships.models import Relationship

from tests.modules.individuals.resources import utils as individual_utils
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
def test_create_read_delete_relationship(flask_app_client):

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

    temp_enc_1 = utils.generate_encounter_instance(
        user_email='enc@user', user_password='encuser', user_full_name='enc user 1'
    )
    enc_1_json = {'encounters': [{'id': str(temp_enc_1.guid)}]}
    temp_enc_1.owner = temp_owner
    response = individual_utils.create_individual(
        flask_app_client, temp_owner, expected_status_code=200, data_in=enc_1_json
    )
    individual_1_guid = response.json['result']['id']

    temp_enc_2 = utils.generate_encounter_instance(
        user_email='enc@user', user_password='encuser', user_full_name='enc user 1'
    )
    enc_2_json = {'encounters': [{'id': str(temp_enc_2.guid)}]}
    temp_enc_2.owner = temp_owner
    response = individual_utils.create_individual(
        flask_app_client, temp_owner, expected_status_code=200, data_in=enc_2_json
    )
    individual_2_guid = response.json['result']['id']

    relationship_json = {
        'individual_1_guid': individual_1_guid,
        'individual_2_guid': individual_2_guid,
        'individual_1_role': 'Mother',
        'individual_2_role': 'Calf',
    }
    response = relationship_utils.create_relationship(
        flask_app_client, temp_owner, expected_status_code=200, data_in=relationship_json
    )
    relationship_guid = response.json['result']['id']

    # finally:
    individual_utils.delete_individual(flask_app_client, temp_owner, individual_1_guid)
    individual_utils.delete_individual(flask_app_client, temp_owner, individual_2_guid)
    relationship_utils.delete_relationship(
        flask_app_client, temp_owner, relationship_guid
    )
    temp_enc_1.delete_cascade()
    temp_enc_2.delete_cascade()
