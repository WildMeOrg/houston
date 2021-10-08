# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import sqlalchemy

import logging

from app.modules.individuals.models import Individual
from app.modules.relationships.models import Relationship

from tests.modules.individuals.resources import utils as individual_utils


def test_relationship_instantiation(db, temp_user,):

    individual_1 = Individual()
    individual_2 = Individual()

    relationship_1_role = "Mother"
    relationship_2_role = "Calf"

    relationship = Relationship(individual_1, individual_2, relationship_1_role, relationship_2_role)

    assert relationship.individual_1 and relationship.individual_1 is individual_1
    assert relationship.individual_2 and relationship.individual_2 is individual_2

    assert relationship.individual_1_role and relationship.individual_1_role is individual_1
    assert relationship.individual_2_role and relationship.individual_2_role is individual_2
