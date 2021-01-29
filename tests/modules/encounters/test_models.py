# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring


def test_encounter_add_owner(db):

    from app.modules.users.models import User
    from app.modules.encounters.models import Encounter

    test_user = User(
        email='testuser@localhost',
        password='testpassword',
        full_name='Gregor Samsa ',
    )

    test_encounter = Encounter()

    with db.session.begin():
        db.session.add(test_encounter)
        db.session.add(test_user)

    db.session.refresh(test_encounter)
    db.session.refresh(test_user)

    assert test_encounter.get_owner() is None

    # need to set up association object, but this works
    test_user.owned_encounters.append(test_encounter)

    with db.session.begin():
        db.session.add(test_encounter)
        db.session.add(test_user)

    db.session.refresh(test_encounter)
    db.session.refresh(test_user)

    assert test_encounter.get_owner() is not None
    assert test_encounter.get_owner().guid == test_user.guid
