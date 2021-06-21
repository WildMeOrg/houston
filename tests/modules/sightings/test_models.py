# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import logging

from app.modules.users.models import User


def test_sighting_create_and_add_encounters(db):

    from app.modules.sightings.models import Sighting, SightingStage
    from app.modules.encounters.models import Encounter

    test_sighting = Sighting(stage=SightingStage.processed)
    owner = User.get_public_user()

    test_encounter_a = Encounter()
    test_encounter_a.owner_guid = owner.guid

    test_encounter_b = Encounter()
    test_encounter_b.owner_guid = owner.guid

    with db.session.begin():
        db.session.add(test_encounter_a)
        db.session.add(test_sighting)

    db.session.refresh(test_encounter_a)
    db.session.refresh(test_sighting)

    assert len(test_sighting.get_encounters()) == 0
    assert test_encounter_a.get_sighting() is None

    test_sighting.add_encounter(test_encounter_a)

    with db.session.begin():
        db.session.add(test_encounter_a)
        db.session.add(test_sighting)

    assert len(test_sighting.get_encounters()) == 1
    assert test_encounter_a.get_sighting() is not None

    test_sighting.add_encounter(test_encounter_b)

    with db.session.begin():
        db.session.add(test_encounter_b)
        db.session.add(test_sighting)

    # making sure i didn't accidentally set up a 1 to 1
    assert len(test_sighting.get_encounters()) == 2

    logging.info(test_sighting.get_encounters())
    logging.info(test_encounter_a.get_sighting())


def test_sighting_ensure_no_duplicate_encounters(db):
    from app.modules.sightings.models import Sighting, SightingStage
    from app.modules.encounters.models import Encounter

    test_sighting = Sighting(stage=SightingStage.processed)
    owner = User.get_public_user()

    test_encounter = Encounter()
    test_encounter.owner_guid = owner.guid

    with db.session.begin():
        db.session.add(test_encounter)
        db.session.add(test_sighting)

    db.session.refresh(test_encounter)
    db.session.refresh(test_sighting)

    test_sighting.add_encounter(test_encounter)

    with db.session.begin():
        db.session.add(test_encounter)
        db.session.add(test_sighting)

    db.session.refresh(test_encounter)
    db.session.refresh(test_sighting)

    assert len(test_sighting.get_encounters()) == 1
    assert test_encounter.get_sighting() is not None

    # try adding again, shouldn't let ya
    test_sighting.add_encounter(test_encounter)

    with db.session.begin():
        db.session.add(test_encounter)
        db.session.add(test_sighting)

    db.session.refresh(test_encounter)
    db.session.refresh(test_sighting)

    assert len(test_sighting.get_encounters()) == 1
    assert test_encounter.get_sighting() is not None

    logging.info(test_sighting.get_encounters())
    logging.info(test_encounter.get_sighting())
