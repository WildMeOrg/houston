# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import os
import pathlib
import pytest
import shutil

from tests.utils import module_unavailable
from tests.extensions.tus import utils as tus_utils


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_create_mission_collection_from_tus(flask_app, db, data_manager_1, test_root):

    from app.modules.missions.models import MissionCollection

    tid = tus_utils.get_transaction_id()  # '11111111-1111-1111-1111-111111111111'

    # first no such dir exists
    transaction_dir = pathlib.Path(
        tus_utils.tus_upload_dir(flask_app, transaction_id=tid)
    )
    if (transaction_dir).exists():
        shutil.rmtree(transaction_dir)
    with pytest.raises(OSError):
        sub = MissionCollection.create_from_tus('PYTEST', data_manager_1, tid)

    # now with a file dir+files but ask for wrong one
    tid, valid_file = tus_utils.prep_tus_dir(test_root)
    with pytest.raises(AssertionError):
        sub = MissionCollection.create_from_tus(
            'PYTEST', data_manager_1, tid, paths={'fail.jpg'}
        )

    # test with explicit paths (should succeed)
    sub = MissionCollection.create_from_tus(
        'PYTEST', data_manager_1, tid, paths={valid_file}
    )
    assert len(sub.assets) == 1
    assert sub.assets[0].path == valid_file
    if os.path.exists(sub.get_absolute_path()):
        shutil.rmtree(sub.get_absolute_path())
    sub.delete()

    # test with no paths (should succeed same as above)
    tid, valid_file = tus_utils.prep_tus_dir(test_root)
    sub = MissionCollection.create_from_tus('PYTEST', data_manager_1, tid)
    assert len(sub.assets) == 1
    assert sub.assets[0].path == valid_file
    if os.path.exists(sub.get_absolute_path()):
        shutil.rmtree(sub.get_absolute_path())
    sub.delete()
