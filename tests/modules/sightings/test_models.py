# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import logging

import pytest

import tests.utils as test_utils
from app.modules.users.models import User
from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_sighting_create_and_add_encounters(db):
    from app.modules.sightings.models import Sighting, SightingStage

    test_sighting = Sighting(stage=SightingStage.processed)
    test_sighting.time = test_utils.complex_date_time_now()
    owner = User.get_public_user()

    test_encounter_a = test_utils.generate_owned_encounter(owner)

    test_encounter_b = test_utils.generate_owned_encounter(owner)

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

    test_encounter_a.delete()
    test_encounter_b.delete()
    test_sighting.delete()


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_basic_pipeline_status(db):
    from app.modules.sightings.models import Sighting, SightingStage

    sighting = Sighting(stage=SightingStage.processed)
    sighting.time = test_utils.complex_date_time_now()

    with db.session.begin():
        db.session.add(sighting)

    pipeline_status = sighting.get_pipeline_status()

    curation_status = {
        '_note': 'migrated sighting; curation status fabricated',
        'skipped': True,
        'start': sighting.created.isoformat() + 'Z',
        'end': sighting.created.isoformat() + 'Z',
        'inProgress': False,
        'complete': True,
        'failed': False,
        'progress': 1.0,
    }
    assert pipeline_status['curation'] == curation_status
    sighting.delete()


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_sighting_ensure_no_duplicate_encounters(db):
    from app.modules.sightings.models import Sighting, SightingStage

    test_sighting = Sighting(stage=SightingStage.processed)
    test_sighting.time = test_utils.complex_date_time_now()
    owner = User.get_public_user()

    test_encounter = test_utils.generate_owned_encounter(owner)

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

    test_sighting.delete()
    test_encounter.delete()
