# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import datetime
import logging
from unittest import mock
import uuid
import pytest

from app.modules.users.models import User
import tests.utils as test_utils

from tests.utils import extension_unavailable, module_unavailable


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


@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
def test_sighting_jobs(db, request, researcher_1):
    from app.modules.sightings.models import Sighting, SightingStage

    ia_config1 = [
        {
            'matching_set': {'test': 0},
            'algorithms': {'algorithm_id': 'algorithm1'},
        },
    ]
    ia_config2 = [
        {
            'matching_set': {'test': 1},
            'algorithms': {'algorithm_id': 'algorithm2'},
        },
    ]
    from app.modules.asset_groups.models import AssetGroupSighting, AssetGroup

    group = AssetGroup(owner=researcher_1)

    sighting_config1 = test_utils.dummy_sighting_info()
    sighting_config1['idConfigs'] = ia_config1
    ags1 = AssetGroupSighting(
        asset_group=group,
        sighting_config=sighting_config1,
        detection_configs=test_utils.dummy_detection_info(),
    )
    ags1.setup()
    sighting_config2 = test_utils.dummy_sighting_info()
    sighting_config2['idConfigs'] = ia_config2
    ags2 = AssetGroupSighting(
        asset_group=group,
        sighting_config=sighting_config2,
        detection_configs=test_utils.dummy_detection_info(),
    )
    ags2.setup()

    sighting1 = ags1.sighting[0]
    sighting2 = ags2.sighting[0]
    # Both created sightings were un-reviewed so take them back to identification
    sighting1.stage = SightingStage.identification
    sighting2.stage = SightingStage.identification

    mock_acm = mock.patch('app.modules.sightings.models.current_app.acm')
    mock_acm.start()
    request.addfinalizer(mock_acm.stop)

    job_id1 = uuid.uuid4()
    job_id2 = uuid.uuid4()
    job_ids = [job_id2, job_id1]
    mock_uuid = mock.patch(
        'app.modules.sightings.models.uuid.uuid4', side_effect=job_ids.pop
    )
    mock_uuid.start()
    request.addfinalizer(mock_uuid.stop)

    now = datetime.datetime(2021, 7, 7, 23, 43, 55)
    aid1 = '00000000-0000-0000-0000-000000000001'
    sage1 = '00000000-0000-0000-0000-000000000002'
    aid2 = '00000000-0000-0000-0000-000000000003'
    sage2 = '00000000-0000-0000-0000-000000000004'
    with mock.patch('datetime.datetime') as mock_datetime:
        mock_datetime.utcnow.return_value = now
        with mock.patch.object(sighting1, 'build_identification_request'):
            sighting1.send_identification(0, 'algorithm_id', aid1, sage1)
            # sighting1.send_identification('config2', 'algorithm_id', 'aid1', 'sage_aid1')
        with mock.patch.object(sighting2, 'build_identification_request'):
            sighting2.send_identification(0, 'algorithm_id', aid2, sage2)

    assert Sighting.query.get(sighting1.guid).jobs == {
        str(job_id1): {
            'matching_set': {'test': 0},
            'algorithm': 'algorithm1',
            'annotation': aid1,
            'annotation_sage_uuid': sage1,
            'active': True,
            'start': now,
        },
    }
    assert Sighting.query.get(sighting2.guid).jobs == {
        str(job_id2): {
            'matching_set': {'test': 1},
            'algorithm': 'algorithm2',
            'annotation': aid2,
            'annotation_sage_uuid': sage2,
            'active': True,
            'start': now,
        },
    }
    group.delete()
