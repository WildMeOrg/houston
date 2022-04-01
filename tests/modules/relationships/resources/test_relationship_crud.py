# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging

from tests.utils import module_unavailable
from datetime import datetime, timedelta  # NOQA
import pytest
import uuid


log = logging.getLogger(__name__)


@pytest.mark.skipif(
    module_unavailable('individuals', 'relationships'),
    reason='Individuals or Relationships module disabled',
)
def test_create_read_delete_relationship(
    flask_app_client, researcher_1, request, test_root
):
    from tests.modules.individuals.resources import utils as individual_utils
    from tests.modules.encounters.resources import utils as encounter_utils
    from tests.modules.relationships.resources import utils as relationship_utils
    from app.modules.relationships.models import Relationship

    temp_enc_1 = None
    temp_enc_2 = None
    individual_1_guid = None
    individual_2_guid = None

    headers = (('x-allow-delete-cascade-sighting', True),)

    response = encounter_utils.create_encounter(
        flask_app_client, researcher_1, request, test_root
    )

    temp_enc_1_guid = response['encounters'][0]
    request.addfinalizer(
        lambda: encounter_utils.delete_encounter(
            flask_app_client, researcher_1, temp_enc_1_guid, headers=headers
        )
    )

    from app.modules.encounters.models import Encounter

    temp_enc_1 = Encounter.query.get(temp_enc_1_guid)

    enc_1_json = {'encounters': [{'id': str(temp_enc_1_guid)}]}
    temp_enc_1.owner = researcher_1
    response = individual_utils.create_individual(
        flask_app_client, researcher_1, expected_status_code=200, data_in=enc_1_json
    )
    individual_1_guid = response.json['guid']
    request.addfinalizer(
        lambda: individual_utils.delete_individual(
            flask_app_client, researcher_1, individual_1_guid
        )
    )

    response = encounter_utils.create_encounter(
        flask_app_client, researcher_1, request, test_root
    )
    temp_enc_2_guid = response['encounters'][0]
    request.addfinalizer(
        lambda: encounter_utils.delete_encounter(
            flask_app_client, researcher_1, temp_enc_2_guid, headers=headers
        )
    )

    enc_2_json = {'encounters': [{'id': str(temp_enc_2_guid)}]}

    temp_enc_2 = Encounter.query.get(temp_enc_2_guid)
    temp_enc_2.owner = researcher_1
    response = individual_utils.create_individual(
        flask_app_client, researcher_1, expected_status_code=200, data_in=enc_2_json
    )
    individual_2_guid = response.json['guid']
    request.addfinalizer(
        lambda: individual_utils.delete_individual(
            flask_app_client, researcher_1, individual_2_guid
        )
    )

    relationship_json = {
        'individual_1_guid': individual_1_guid,
        'individual_2_guid': individual_2_guid,
        'individual_1_role': 'Mother',
        'individual_2_role': 'Calf',
        'type': 'Family',
        'start_date': str(datetime.utcnow()),
        'end_date': str(datetime.utcnow() + timedelta(days=1)),
    }
    response = relationship_utils.create_relationship(
        flask_app_client,
        researcher_1,
        expected_status_code=200,
        data_in=relationship_json,
    )

    relationship_guid = response.json['guid']
    request.addfinalizer(
        lambda: relationship_utils.delete_relationship(
            flask_app_client, researcher_1, relationship_guid
        )
    )

    relationship_1 = Relationship.query.get(relationship_guid)

    individual_1_guid = uuid.UUID(individual_1_guid)
    individual_2_guid = uuid.UUID(individual_2_guid)

    assert relationship_1.has_individual(individual_1_guid)
    assert relationship_1.has_individual(individual_2_guid)

    assert (
        relationship_1.get_relationship_role_for_individual(individual_1_guid) == 'Mother'
    )
    assert (
        relationship_1.get_relationship_role_for_individual(individual_2_guid) == 'Calf'
    )

    assert relationship_1.type == 'Family'

    # one day time delta for this test
    assert (
        relationship_1.start_date.date()
        == (relationship_1.end_date - timedelta(days=1)).date()
    )
