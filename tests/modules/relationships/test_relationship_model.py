# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

from app.modules.relationships.models import Relationship

from tests.modules.individuals.resources import utils as indiv_utils
from tests.modules.relationships.resources import utils as relationship_utils

from tests.utils import module_unavailable
import pytest


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
@pytest.mark.skipif(
    module_unavailable('relationships'), reason='Relationships module disabled'
)
def test_relationship_instantiation(db, staff_user, flask_app_client, request):

    response_1 = indiv_utils.create_individual_with_encounter(
        db,
        flask_app_client,
        staff_user,
        request,
    )

    response_2 = indiv_utils.create_individual_with_encounter(
        db,
        flask_app_client,
        staff_user,
        request,
    )

    individual_1_guid = response_1['id']
    individual_2_guid = response_2['id']

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
