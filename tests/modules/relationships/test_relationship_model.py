# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import uuid

import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('individuals', 'relationships'),
    reason='Individuals and/or Relationships module disabled',
)
def test_relationship_instantiation(db, staff_user, flask_app_client, request, test_root):
    from app.modules.relationships.models import Relationship
    from app.modules.site_settings.models import SiteSetting
    from tests.modules.individuals.resources import utils as indiv_utils
    from tests.modules.relationships.resources import utils as relationship_utils

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
    SiteSetting.set_key_value('relationship_type_roles', relationship_type_roles)

    response_1 = indiv_utils.create_individual_and_sighting(
        flask_app_client, staff_user, request, test_root
    )

    response_2 = indiv_utils.create_individual_and_sighting(
        flask_app_client, staff_user, request, test_root
    )

    individual_1_guid = uuid.UUID(response_1['individual'])
    individual_2_guid = uuid.UUID(response_2['individual'])

    relationship = Relationship(
        individual_1_guid, individual_2_guid, mother_role_guid, calf_role_guid
    )

    assert relationship.has_individual(individual_1_guid)
    assert relationship.has_individual(individual_2_guid)

    assert (
        relationship.get_relationship_role_for_individual(individual_1_guid)[0]
        == 'Mother'
    )
    assert (
        relationship.get_relationship_role_for_individual(individual_2_guid)[0] == 'Calf'
    )

    relationship_utils.delete_relationship(
        flask_app_client, staff_user, relationship.guid
    )
