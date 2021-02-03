# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring


def test_individual_add_remove_encounters(encounter_a, encounter_b, empty_individual):

    assert len(empty_individual.encounters) == 0

    empty_individual.encounters.append(encounter_a)

    assert len(empty_individual.encounters) == 1

    empty_individual.encounters.append(encounter_b)

    assert len(empty_individual.encounters) == 2

    assert encounter_a.individual is empty_individual

    assert encounter_b.individual is empty_individual

    empty_individual.encounters.remove(encounter_b)

    assert len(empty_individual.encounters) == 1
