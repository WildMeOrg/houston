# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import pytest
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('names', 'individuals'), reason='Individual/Names module disabled'
)
def test_names_crud(db, researcher_1, empty_individual, request):
    from app.modules.individuals.models import Individual

    # from app.modules.names.models import Name

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
