# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import os
import pathlib
import shutil

import pytest

from tests.extensions.tus import utils as tus_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_create_mission_collection_from_tus(flask_app, db, admin_user, test_root):

    from app.modules.missions.models import Mission, MissionCollection
    from app.utils import HoustonException

    temp_mission = Mission(
        title='Temp Mission',
        owner=admin_user,
    )
    with db.session.begin():
        db.session.add(temp_mission)
    db.session.refresh(temp_mission)

    tid = tus_utils.get_transaction_id()  # '11111111-1111-1111-1111-111111111111'

    # first no such dir exists
    transaction_dir = pathlib.Path(
        tus_utils.tus_upload_dir(flask_app, transaction_id=tid)
    )
    if (transaction_dir).exists():
        shutil.rmtree(transaction_dir)
    with pytest.raises(HoustonException):
        sub, _ = MissionCollection.create_from_tus(
            'PYTEST', admin_user, tid, mission=temp_mission
        )

    # now with a file dir+files but ask for wrong one
    tid, valid_file = tus_utils.prep_tus_dir(test_root)
    with pytest.raises(HoustonException):
        sub, _ = MissionCollection.create_from_tus(
            'PYTEST', admin_user, tid, mission=temp_mission, paths={'fail.jpg'}
        )

    # test with explicit paths (should succeed)
    sub, _ = MissionCollection.create_from_tus(
        'PYTEST',
        admin_user,
        tid,
        mission=temp_mission,
        paths={valid_file},
    )
    assert len(sub.assets) == 1
    assert sub.assets[0].path == valid_file
    if os.path.exists(sub.get_absolute_path()):
        shutil.rmtree(sub.get_absolute_path())
    sub.delete()

    # test with no paths (should succeed same as above)
    tid, valid_file = tus_utils.prep_tus_dir(test_root)
    sub, _ = MissionCollection.create_from_tus(
        'PYTEST', admin_user, tid, mission=temp_mission
    )
    assert len(sub.assets) == 1
    assert sub.assets[0].path == valid_file
    if os.path.exists(sub.get_absolute_path()):
        shutil.rmtree(sub.get_absolute_path())
    sub.delete()

    temp_mission.delete()
