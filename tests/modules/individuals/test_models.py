# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring


def test_individual_add_remove_retrieve_encounters(
    encounter_a, encounter_b, empty_individual
):

    assert len(empty_individual.encounters) == 0

    empty_individual.encounters.append(encounter_a)

    assert len(empty_individual.encounters) == 1

    empty_individual.encounters.append(encounter_b)

    assert len(empty_individual.encounters) == 2
    assert len(empty_individual.get_encounters()) == 2

    assert encounter_a.individual is empty_individual

    assert encounter_b.individual is empty_individual

    empty_individual.encounters.remove(encounter_b)

    assert len(empty_individual.encounters) == 1
    assert len(empty_individual.get_encounters()) == 1


def test_individual_ownership(encounter_a, encounter_b, empty_individual):
    empty_individual.encounters.append(encounter_a)

    from app.modules.users.models import User

    new_owner = User(email='test2@user', password='testuser', full_name='Test User 2')

    assert not new_owner.owns_object(empty_individual)

    encounter_b.owner = new_owner
    empty_individual.encounters.append(encounter_b)

    assert new_owner.owns_object(empty_individual)
