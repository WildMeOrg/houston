# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import sqlalchemy

import logging

from app.modules.individuals.models import Individual
from app.modules.relationships.models import Relationship

from tests.utils import module_unavailable
import pytest


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
@pytest.mark.skipif(
    module_unavailable('relationships'), reason='Relationships module disabled'
)
def test_relationship_instantiation():

    individual_1 = Individual()
    individual_2 = Individual()

    relationship_role_1 = 'Mother'
    relationship_role_2 = 'Calf'

    relationship = Relationship(
        individual_1, individual_2, relationship_role_1, relationship_role_2
    )

    assert relationship.has_individual(individual_1.guid)
    assert relationship.has_individual(individual_2.guid)

    assert (
        relationship.get_relationship_role_for_individual(individual_1.guid) == 'Mother'
    )
    assert relationship.get_relationship_role_for_individual(individual_2.guid) == 'Calf'
