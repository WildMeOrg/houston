# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.missions.resources.utils as mission_collection_utils
import tests.modules.assets.resources.utils as asset_utils
import tests.extensions.tus.utils as tus_utils
from tests import utils as test_utils
import pytest
import pathlib
import shutil
import os

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_user_read_permissions(
    flask_app_client,
    data_manager_1,
    readonly_user,
    db,
    test_clone_mission_collection_data,
):
    # Clone as the researcher user and then try to reread as both researcher and readonly user,
    # read by researcher user should succeed, read by readonly user should be blocked
    clone = mission_collection_utils.clone_mission_collection(
        flask_app_client,
        data_manager_1,
        test_clone_mission_collection_data['mission_collection_uuid'],
    )
    asset_utils.read_asset(
        flask_app_client,
        data_manager_1,
        test_clone_mission_collection_data['asset_uuids'][0],
    )
    mission_collection_utils.read_mission_collection(
        flask_app_client,
        data_manager_1,
        test_clone_mission_collection_data['mission_collection_uuid'],
    )
    asset_utils.read_asset(
        flask_app_client,
        readonly_user,
        test_clone_mission_collection_data['asset_uuids'][0],
        403,
    )
    mission_collection_utils.read_mission_collection(
        flask_app_client,
        readonly_user,
        test_clone_mission_collection_data['mission_collection_uuid'],
        403,
    )
    # and as no user
    mission_collection_utils.read_mission_collection(
        flask_app_client,
        None,
        test_clone_mission_collection_data['mission_collection_uuid'],
        401,
    )
    clone.cleanup()


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_create_patch_mission_collection(
    flask_app, flask_app_client, data_manager_1, readonly_user, test_root, db
):
    from app.modules.missions.models import MissionCollection

    # pylint: disable=invalid-name
    mission_collection_guid = None
    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    try:
        tid = tus_utils.get_transaction_id()  # '11111111-1111-1111-1111-111111111111'

        # first no such dir exists
        transaction_dir = pathlib.Path(
            tus_utils.tus_upload_dir(flask_app, transaction_id=tid)
        )
        if (transaction_dir).exists():
            shutil.rmtree(transaction_dir)

        # test with explicit paths (should succeed)
        tid, valid_file = tus_utils.prep_tus_dir(test_root)
        temp_mission_collection = MissionCollection.create_from_tus(
            'PYTEST', data_manager_1, tid, paths={valid_file}
        )
        assert len(temp_mission_collection.assets) == 1
        assert temp_mission_collection.assets[0].path == valid_file
        mission_collection_guid = temp_mission_collection.guid

        # reassign ownership
        patch_data = [
            test_utils.patch_add_op(
                'description', 'This is a test mission_collection, kindly ignore'
            ),
        ]

        # Try to patch as non owner and validate it fails
        mission_collection_utils.patch_mission_collection(
            flask_app_client, readonly_user, mission_collection_guid, patch_data, 403
        )

        # Should pass as owner
        patch_response = mission_collection_utils.patch_mission_collection(
            flask_app_client, data_manager_1, mission_collection_guid, patch_data
        )

        assert patch_response.json['description'] == patch_data[0]['value']
        assert patch_response.json['guid'] == str(mission_collection_guid)

        db.session.refresh(temp_mission_collection)

        # Readonly user should not be able to delete
        mission_collection_utils.delete_mission_collection(
            flask_app_client, readonly_user, mission_collection_guid, 403
        )

        # researcher should
        mission_collection_utils.delete_mission_collection(
            flask_app_client, data_manager_1, mission_collection_guid
        )
        # temp_mission_collection should be already deleted on gitlab
        assert not MissionCollection.is_on_remote(str(temp_mission_collection.guid))
    finally:
        if os.path.exists(temp_mission_collection.get_absolute_path()):
            shutil.rmtree(temp_mission_collection.get_absolute_path())

        temp_mission_collection.delete()

        tus_utils.cleanup_tus_dir(transaction_id)
        # Restore original state
        temp_mission_collection = MissionCollection.query.get(mission_collection_guid)
        if temp_mission_collection is not None:
            temp_mission_collection.delete()
