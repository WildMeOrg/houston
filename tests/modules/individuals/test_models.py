# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_individual_add_remove_encounters(encounter_1, encounter_2, empty_individual):

    assert len(empty_individual.encounters) == 0

    empty_individual.add_encounter(encounter_1)
    assert len(empty_individual.get_encounters()) == 1

    empty_individual.add_encounter(encounter_2)
    assert len(empty_individual.get_encounters()) == 2

    assert encounter_1.individual is empty_individual
    assert encounter_2.individual is empty_individual

    empty_individual.remove_encounter(encounter_2)
    assert len(empty_individual.get_encounters()) == 1

    empty_individual.remove_encounter(encounter_1)

    encounter_list = [encounter_1, encounter_2]
    empty_individual.add_encounters(encounter_list)
    assert len(empty_individual.get_encounters()) == 2
    assert encounter_1.individual is empty_individual
    assert encounter_2.individual is empty_individual

    # restore to original state
    empty_individual.encounters = []
    assert len(empty_individual.encounters) == 0


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_individual_ownership(encounter_1, encounter_2, empty_individual):
    empty_individual.encounters.append(encounter_1)

    from app.modules.users.models import User

    new_owner = User(
        email='new_owner@user', password='owneruser', full_name='Test User 2'
    )

    assert not new_owner.owns_object(empty_individual)
    encounter_2.owner = new_owner
    empty_individual.encounters.append(encounter_2)
    assert new_owner.owns_object(empty_individual)

    # restore to original state
    empty_individual.encounters = []
    assert len(empty_individual.encounters) == 0
    encounter_2.owner = None
    assert encounter_2.owner is None
