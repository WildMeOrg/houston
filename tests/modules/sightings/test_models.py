# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import datetime
import logging
from unittest import mock
import uuid

from app.modules.users.models import User
import tests.utils as test_utils


def test_sighting_create_and_add_encounters(db):

    from app.modules.sightings.models import Sighting, SightingStage

    test_sighting = Sighting(stage=SightingStage.processed)
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


def test_sighting_ensure_no_duplicate_encounters(db):
    from app.modules.sightings.models import Sighting, SightingStage

    test_sighting = Sighting(stage=SightingStage.processed)
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


def test_sighting_jobs(db, request, researcher_1):
    from app.modules.sightings.models import Sighting, SightingStage

    example_ia_configs = {
        'config1': {
            'matchingSetDataOwners': ['user1'],
            'algorithms': {'algorithm_id': 'algorithm1'},
        },
        'config2': {
            'matchingSetDataOwners': ['user2'],
            'algorithms': {'algorithm_id': 'algorithm2'},
        },
    }

    from app.modules.asset_groups.models import AssetGroupSighting, AssetGroup

    group = AssetGroup(owner=researcher_1)
    ags = AssetGroupSighting(asset_group=group)
    ags.config = {'idConfigs': example_ia_configs}

    sighting1 = Sighting(
        stage=SightingStage.identification,
        asset_group_sighting=ags,
    )
    sighting2 = Sighting(
        stage=SightingStage.identification,
        asset_group_sighting=ags,
    )
    with db.session.begin():
        db.session.add(sighting1)
        db.session.add(sighting2)
    request.addfinalizer(sighting1.delete)
    request.addfinalizer(sighting2.delete)
    mock_acm = mock.patch('app.modules.sightings.models.current_app.acm')
    mock_acm.start()
    request.addfinalizer(mock_acm.stop)

    job_id1 = uuid.uuid4()
    job_id2 = uuid.uuid4()
    job_id3 = uuid.uuid4()
    job_ids = [job_id3, job_id2, job_id1]
    mock_uuid = mock.patch(
        'app.modules.sightings.models.uuid.uuid4', side_effect=job_ids.pop
    )
    mock_uuid.start()
    request.addfinalizer(mock_uuid.stop)

    now = datetime.datetime(2021, 7, 7, 23, 43, 55)
    with mock.patch('datetime.datetime') as mock_datetime:
        mock_datetime.utcnow.return_value = now
        with mock.patch.object(sighting1, 'build_identification_request'):
            sighting1.send_identification('config1', 'algorithm_id', 'aid1', 'sage_aid1')
            sighting1.send_identification('config2', 'algorithm_id', 'aid1', 'sage_aid1')
        with mock.patch.object(sighting2, 'build_identification_request'):
            sighting2.send_identification('config2', 'algorithm_id', 'aid2', 'sage_aid2')

    assert Sighting.query.get(sighting1.guid).jobs == {
        str(job_id1): {
            'matching_set': ['user1'],
            'algorithm': 'algorithm1',
            'annotation': 'aid1',
            'active': True,
            'start': now,
        },
        str(job_id2): {
            'matching_set': ['user2'],
            'algorithm': 'algorithm2',
            'annotation': 'aid1',
            'active': True,
            'start': now,
        },
    }
    assert Sighting.query.get(sighting2.guid).jobs == {
        str(job_id3): {
            'matching_set': ['user2'],
            'algorithm': 'algorithm2',
            'annotation': 'aid2',
            'active': True,
            'start': now,
        },
    }
    group.delete()
