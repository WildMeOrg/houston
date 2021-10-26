# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import tests.utils as test_utils
import logging
import pytest

from tests.utils import module_unavailable


log = logging.getLogger(__name__)


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_encounter_add_owner(db):
    from app.modules.users.models import User

    test_user = User(
        email='testuser@localhost',
        password='testpassword',
        full_name='Gregor Samsa ',
    )

    public_owner = User.get_public_user()
    test_encounter = test_utils.generate_owned_encounter(public_owner)

    with db.session.begin():
        db.session.add(test_encounter)
        db.session.add(test_user)

    db.session.refresh(test_encounter)
    db.session.refresh(test_user)

    assert test_encounter.get_owner() is public_owner

    test_user.owned_encounters.append(test_encounter)

    with db.session.begin():
        db.session.add(test_encounter)
        db.session.add(test_user)

    db.session.refresh(test_encounter)
    db.session.refresh(test_user)

    assert test_encounter.get_owner() is not None
    assert test_encounter.get_owner().guid == test_user.guid
    test_encounter.delete()


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_encounter_set_individual(db, empty_individual, encounter_1):

    assert empty_individual is not None
    encounter_1.set_individual(empty_individual)
    assert encounter_1.individual is not None
    assert encounter_1.individual.guid == empty_individual.guid


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_owned_encounters_ordering(db, request):
    from app.modules.encounters.models import Encounter
    from app.modules.users.models import User

    public_owner = User.get_public_user()
    encounters = []
    for i in range(10):
        encounters.append(Encounter(owner=public_owner))

    encounters.sort(key=lambda e: e.guid)

    def cleanup():
        for encounter in encounters:
            db.session.delete(encounter)

    request.addfinalizer(cleanup)

    assert public_owner.owned_encounters == encounters
