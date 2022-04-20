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
    flask_app_client, admin_user, researcher_1, request, test_root
):
    from tests.modules.individuals.resources import utils as individual_utils
    from tests.modules.encounters.resources import utils as encounter_utils
    from tests.modules.relationships.resources import utils as relationship_utils
    from tests.modules.site_settings.resources import utils as site_settings_utils
    from app.modules.relationships.models import Relationship

    family_type_guid = '49e85f81-c11a-42be-9097-d22c61345ed8'
    mother_role_guid = '1b62eb1a-0b80-4c2d-b914-923beba8863c'
    calf_role_guid = 'ea5dbbb3-cc47-4d44-b460-2518a25dcb13'
    relationship_type_roles = {
        family_type_guid: {
            'guid': family_type_guid,
            'label': 'Family',
            'roles': [
                {'guid': mother_role_guid, 'label': 'Mother'},
                {'guid': calf_role_guid, 'label': 'Calf'},
            ],
        },
    }
    site_settings_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        {'_value': relationship_type_roles},
        conf_key='relationship_type_roles',
    )

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

    enc_1_json = {
        'names': [{'context': 'FirstName', 'value': 'Mommy'}],
        'encounters': [{'id': str(temp_enc_1_guid)}],
    }
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
        'individual_1_role_guid': mother_role_guid,
        'individual_2_role_guid': calf_role_guid,
        'type_guid': family_type_guid,
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
    assert sorted(
        response.json['individual_members'], key=lambda a: a['individual_role_guid']
    ) == [
        {
            'individual_guid': individual_1_guid,
            'individual_role_label': 'Mother',
            'individual_role_guid': mother_role_guid,
        },
        {
            'individual_guid': individual_2_guid,
            'individual_role_label': 'Calf',
            'individual_role_guid': calf_role_guid,
        },
    ]

    response = relationship_utils.read_relationship(
        flask_app_client,
        researcher_1,
        relationship_guid,
        expected_status_code=200,
    )
    assert sorted(
        response.json['individual_members'], key=lambda a: a['individual_role_guid']
    ) == [
        {
            'individual_guid': individual_1_guid,
            'individual_role_label': 'Mother',
            'individual_role_guid': mother_role_guid,
        },
        {
            'individual_guid': individual_2_guid,
            'individual_role_label': 'Calf',
            'individual_role_guid': calf_role_guid,
        },
    ]

    relationship_1 = Relationship.query.get(relationship_guid)

    individual_1_guid = uuid.UUID(individual_1_guid)
    individual_2_guid = uuid.UUID(individual_2_guid)

    assert relationship_1.has_individual(individual_1_guid)
    assert relationship_1.has_individual(individual_2_guid)

    assert (
        relationship_1.get_relationship_role_for_individual(individual_1_guid)[0]
        == 'Mother'
    )
    assert (
        relationship_1.get_relationship_role_for_individual(individual_2_guid)[0]
        == 'Calf'
    )

    assert str(relationship_1.type_guid) == family_type_guid
    assert relationship_1.type_label == 'Family'

    # one day time delta for this test
    assert (
        relationship_1.start_date.date()
        == (relationship_1.end_date - timedelta(days=1)).date()
    )

    response = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_1_guid
    )
    for relationship in response.json['relationships']:
        relationship['individual_members'].sort(key=lambda a: a['individual_role_guid'])
    assert response.json['relationships'] == [
        {
            'guid': str(relationship_1.guid),
            'type_label': 'Family',
            'type_guid': family_type_guid,
            'individual_members': [
                {
                    'individual_role_label': 'Mother',
                    'individual_role_guid': mother_role_guid,
                    'individual_guid': str(individual_1_guid),
                    'individual_first_name': 'Mommy',
                },
                {
                    'individual_role_label': 'Calf',
                    'individual_role_guid': calf_role_guid,
                    'individual_guid': str(individual_2_guid),
                    'individual_first_name': None,
                },
            ],
        }
    ]
