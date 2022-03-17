# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

from tests.utils import module_unavailable
import pytest
import uuid


@pytest.mark.skipif(
    module_unavailable('individuals', 'relationships'),
    reason='Individuals and/or Relationships module disabled',
)
def test_relationship_instantiation(db, staff_user, flask_app_client, request, test_root):
    from app.modules.relationships.models import Relationship

    from tests.modules.individuals.resources import utils as indiv_utils
    from tests.modules.relationships.resources import utils as relationship_utils

    response_1 = indiv_utils.create_individual_and_sighting(
        flask_app_client, staff_user, request, test_root
    )

    response_2 = indiv_utils.create_individual_and_sighting(
        flask_app_client, staff_user, request, test_root
    )

    individual_1_guid = uuid.UUID(response_1['individual'])
    individual_2_guid = uuid.UUID(response_2['individual'])

    relationship_role_1 = 'Mother'
    relationship_role_2 = 'Calf'

    relationship = Relationship(
        individual_1_guid, individual_2_guid, relationship_role_1, relationship_role_2
    )

    assert relationship.has_individual(individual_1_guid)
    assert relationship.has_individual(individual_2_guid)

    assert (
        relationship.get_relationship_role_for_individual(individual_1_guid) == 'Mother'
    )
    assert relationship.get_relationship_role_for_individual(individual_2_guid) == 'Calf'

    relationship_utils.delete_relationship(
        flask_app_client, staff_user, relationship.guid
    )
