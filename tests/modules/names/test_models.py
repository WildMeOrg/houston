# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import pytest
import sqlalchemy
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('names', 'individuals'), reason='Individual/Names module disabled'
)
def test_names_crud(db, researcher_1, researcher_2, empty_individual, request):
    from app.modules.individuals.models import Individual

    context = 'test-context'
    request.addfinalizer(empty_individual.delete)
    with db.session.begin(subtransactions=True):
        db.session.add(empty_individual)

    test_name = 'test-name-1'
    empty_individual.add_name(context, test_name, researcher_1)

    test_indiv = Individual.query.get(empty_individual.guid)
    assert test_indiv
    assert len(test_indiv.names) == 1
    assert test_indiv.names[0].context == context
    assert test_indiv.names[0].value == test_name

    # twiddle the preferring users
    test_indiv.names[0].add_preferring_user(researcher_1)
    pref_users = test_indiv.names[0].get_preferring_users()
    assert len(pref_users) == 1
    assert pref_users[0] == researcher_1

    # should fail, as they are already added
    try:
        test_indiv.names[0].add_preferring_user(researcher_1)
    except ValueError:
        pass

    test_indiv.names[0].remove_preferring_user(researcher_1)
    pref_users = test_indiv.names[0].get_preferring_users()
    assert len(pref_users) == 0

    # add a name with existing context
    try:
        empty_individual.add_name(context, test_name, researcher_2)
    except sqlalchemy.exc.IntegrityError as ie:
        assert 'duplicate key' in str(ie)

    another_context = 'test-context-2'
    empty_individual.add_name(another_context, test_name, researcher_2)
    test_indiv = Individual.query.get(empty_individual.guid)
    assert test_indiv
    assert len(test_indiv.names) == 2

    # test some of the get_ types
    test = empty_individual.get_names()
    assert len(test) == 2
    test = empty_individual.get_names_for_value(test_name)
    assert len(test) == 2
    assert test[0].value == test_name
    test = empty_individual.get_names_for_value('no such value')
    assert not test
    test = empty_individual.get_name_for_context(context)
    assert test
    assert test.context == context
    test = empty_individual.get_name_for_context('no such context')
    assert not test

    # now removal
    test = empty_individual.remove_name_for_context('no such context')
    assert not test
    test = empty_individual.remove_names_for_value('no such value')
    assert test == 0
    test = empty_individual.remove_name_for_context(another_context)
    assert test
    assert len(empty_individual.names) == 1
    # add back in so we have 2 with test_name value
    empty_individual.add_name(another_context, test_name, researcher_2)
    assert len(empty_individual.names) == 2
    test = empty_individual.remove_names_for_value(test_name)
    assert test == 2
    assert len(empty_individual.names) == 0

    # attempt to remove a name from wrong individual
    individual2 = Individual()
    request.addfinalizer(individual2.delete)
    with db.session.begin(subtransactions=True):
        db.session.add(individual2)
    name2 = individual2.add_name(context, test_name, researcher_2)
    assert name2
    assert name2.value == test_name
    try:
        empty_individual.remove_name(name2)
    except ValueError as ve:
        assert ' not on ' in str(ve)

    # add one more for good luck, as this will test that the auto-deletion of individual is fine when has names
    empty_individual.add_name(context, test_name, researcher_2)
