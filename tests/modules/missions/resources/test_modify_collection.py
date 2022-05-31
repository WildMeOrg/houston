# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import os
import pathlib
import shutil

import pytest

import tests.extensions.tus.utils as tus_utils
import tests.modules.missions.resources.utils as mission_utils
from tests import utils as test_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_create_patch_mission_collection(
    flask_app, flask_app_client, data_manager_1, readonly_user, test_root, db
):
    from app.modules.missions.models import Mission, MissionCollection

    # pylint: disable=invalid-name
    mission_guid, mission_collection_guid = None, None
    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    transaction_ids = []
    transaction_ids.append(transaction_id)
    try:
        temp_mission = Mission(
            title='Temp Mission',
            owner=data_manager_1,
        )
        with db.session.begin():
            db.session.add(temp_mission)
        db.session.refresh(temp_mission)
        mission_guid = temp_mission.guid

        tid = tus_utils.get_transaction_id()  # '11111111-1111-1111-1111-111111111111'

        # first no such dir exists
        transaction_dir = pathlib.Path(
            tus_utils.tus_upload_dir(flask_app, transaction_id=tid)
        )
        if (transaction_dir).exists():
            shutil.rmtree(transaction_dir)

        # test with explicit paths (should succeed)
        tid, valid_file = tus_utils.prep_tus_dir(test_root)
        transaction_ids.append(tid)
        temp_mission_collection, _ = MissionCollection.create_from_tus(
            'PYTEST',
            data_manager_1,
            tid,
            mission=temp_mission,
            paths={valid_file},
        )
        assert len(temp_mission_collection.assets) == 1
        assert temp_mission_collection.assets[0].path == valid_file
        mission_collection_guid = temp_mission_collection.guid

        # reassign ownership
        patch_data = [
            test_utils.patch_add_op(
                'description', mission_utils.make_name('mission collection')[1]
            ),
        ]

        # Try to patch as non owner and validate it fails
        mission_utils.patch_mission_collection(
            flask_app_client, readonly_user, mission_collection_guid, patch_data, 403
        )

        # Should pass as owner
        patch_response = mission_utils.patch_mission_collection(
            flask_app_client, data_manager_1, mission_collection_guid, patch_data
        )

        assert patch_response.json['description'] == patch_data[0]['value']
        assert patch_response.json['guid'] == str(mission_collection_guid)

        db.session.refresh(temp_mission_collection)

        # Readonly user should not be able to delete
        mission_utils.delete_mission_collection(
            flask_app_client, readonly_user, mission_collection_guid, 403
        )

        # researcher should
        mission_utils.delete_mission_collection(
            flask_app_client, data_manager_1, mission_collection_guid
        )
        # temp_mission_collection should be already deleted on gitlab
        assert not MissionCollection.is_on_remote(str(temp_mission_collection.guid))
    finally:
        # Restore original state
        temp_mission_collection = MissionCollection.query.get(mission_collection_guid)
        if temp_mission_collection is not None:
            if os.path.exists(temp_mission_collection.get_absolute_path()):
                shutil.rmtree(temp_mission_collection.get_absolute_path())

            temp_mission_collection.delete()

        temp_mission = Mission.query.get(mission_guid)
        if temp_mission is not None:
            temp_mission.delete()

        for transaction_id in transaction_ids:
            tus_utils.cleanup_tus_dir(transaction_id)
