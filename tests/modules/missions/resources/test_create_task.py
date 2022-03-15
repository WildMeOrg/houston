# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils
from tests.modules.missions.resources import utils as mission_utils
from tests.utils import random_guid, wait_for_elasticsearch_status
import tests.extensions.tus.utils as tus_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_create_and_delete_mission_task(flask_app_client, data_manager_1, test_root, db):
    # pylint: disable=invalid-name
    from app.modules.missions.models import (
        Mission,
        MissionCollection,
        MissionTask,
        MissionTaskUserAssignment,
        MissionTaskAssetParticipation,
    )

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    transaction_ids = []
    transaction_ids.append(transaction_id)
    mission_guid = None

    try:
        response = mission_utils.create_mission(
            flask_app_client,
            data_manager_1,
            mission_utils.make_name('mission')[1],
        )
        mission_guid = response.json['guid']
        temp_mission = Mission.query.get(mission_guid)

        previous_list = mission_utils.read_all_mission_collections(
            flask_app_client, data_manager_1
        )

        new_mission_collections = []
        for index in range(3):
            transaction_id = str(random_guid())
            tus_utils.prep_tus_dir(test_root, transaction_id=transaction_id)
            transaction_ids.append(transaction_id)

            nonce, description = mission_utils.make_name('mission collection')
            response = mission_utils.create_mission_collection_with_tus(
                flask_app_client,
                data_manager_1,
                description,
                transaction_id,
                temp_mission.guid,
            )
            mission_collection_guid = response.json['guid']
            temp_mission_collection = MissionCollection.query.get(mission_collection_guid)

            new_mission_collections.append((nonce, temp_mission_collection))

        current_list = mission_utils.read_all_mission_collections(
            flask_app_client, data_manager_1
        )
        assert len(previous_list.json) + len(new_mission_collections) == len(
            current_list.json
        )

        nonce, new_mission_collection1 = new_mission_collections[0]
        nonce, new_mission_collection2 = new_mission_collections[1]
        data = [
            utils.set_union_op('search', {}),
            utils.set_difference_op('collections', [str(new_mission_collection1.guid)]),
            utils.set_difference_op(
                'assets', [str(new_mission_collection2.assets[0].guid)]
            ),
        ]

        # Wait for elasticsearch to catch up
        wait_for_elasticsearch_status(flask_app_client, data_manager_1)

        trial = 0
        while True:
            trial += 1

            response = mission_utils.create_mission_task(
                flask_app_client, data_manager_1, mission_guid, data
            )

            mission_task_guid = response.json['guid']
            read_mission_task = MissionTask.query.get(response.json['guid'])
            assert 'New Task: ' in read_mission_task.title
            assert read_mission_task.owner == data_manager_1
            mission_task_assets = read_mission_task.get_assets()

            if len(mission_task_assets) != 0:
                break

            if trial >= 10:
                raise RuntimeError()

        assert len(mission_task_assets) == 1
        nonce, new_mission_collection3 = new_mission_collections[2]
        assert mission_task_assets[0].git_store == new_mission_collection3

        # Try reading it back
        mission_utils.read_mission_task(
            flask_app_client, data_manager_1, mission_task_guid
        )

        # And deleting it
        mission_utils.delete_mission_task(
            flask_app_client, data_manager_1, mission_task_guid
        )
        read_mission_task = MissionTask.query.get(mission_task_guid)
        assert read_mission_task is None

        read_mission_task = MissionTaskUserAssignment.query.filter_by(
            mission_task_guid=mission_task_guid
        ).all()
        assert len(read_mission_task) == 0

        read_mission_task = MissionTaskAssetParticipation.query.filter_by(
            mission_task_guid=mission_task_guid
        ).all()
        assert len(read_mission_task) == 0
    finally:
        if mission_guid:
            mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)
        for transaction_id in transaction_ids:
            tus_utils.cleanup_tus_dir(transaction_id)


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_mission_task_permission(
    flask_app_client,
    admin_user,
    staff_user,
    regular_user,
    data_manager_1,
    data_manager_2,
    test_root,
):
    from app.modules.missions.models import (
        Mission,
        MissionCollection,
    )

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    transaction_ids = []
    transaction_ids.append(transaction_id)
    mission_guid = None

    try:
        response = mission_utils.create_mission(
            flask_app_client,
            data_manager_1,
            mission_utils.make_name('mission')[1],
        )
        mission_guid = response.json['guid']
        temp_mission = Mission.query.get(mission_guid)

        previous_list = mission_utils.read_all_mission_collections(
            flask_app_client, data_manager_1
        )

        new_mission_collections = []
        for index in range(3):
            transaction_id = str(random_guid())
            tus_utils.prep_tus_dir(test_root, transaction_id=transaction_id)
            transaction_ids.append(transaction_id)

            nonce, description = mission_utils.make_name('mission collection')
            response = mission_utils.create_mission_collection_with_tus(
                flask_app_client,
                data_manager_1,
                description,
                transaction_id,
                temp_mission.guid,
            )
            mission_collection_guid = response.json['guid']
            temp_mission_collection = MissionCollection.query.get(mission_collection_guid)

            new_mission_collections.append((nonce, temp_mission_collection))

        current_list = mission_utils.read_all_mission_collections(
            flask_app_client, data_manager_1
        )
        assert len(previous_list.json) + len(new_mission_collections) == len(
            current_list.json
        )

        nonce, new_mission_collection1 = new_mission_collections[0]
        nonce, new_mission_collection2 = new_mission_collections[1]
        data = [
            utils.set_union_op('search', {}),
            utils.set_difference_op('collections', [str(new_mission_collection1.guid)]),
            utils.set_difference_op(
                'assets', [str(new_mission_collection2.assets[0].guid)]
            ),
        ]

        # Wait for elasticsearch to catch up
        wait_for_elasticsearch_status(flask_app_client, data_manager_1)

        response = mission_utils.create_mission_task(
            flask_app_client, data_manager_1, mission_guid, data
        )

        mission_task_guid = response.json['guid']

        # staff user should be able to read anything
        mission_utils.read_mission_task(flask_app_client, staff_user, mission_task_guid)
        mission_utils.read_all_mission_tasks(flask_app_client, staff_user)

        # admin user should be able to read any tasks as well
        mission_utils.read_mission_task(flask_app_client, admin_user, mission_task_guid)
        mission_utils.read_all_mission_tasks(flask_app_client, admin_user)

        # user that created task can read it back plus the list
        mission_utils.read_mission_task(
            flask_app_client, data_manager_1, mission_task_guid
        )
        list_response = mission_utils.read_all_mission_tasks(
            flask_app_client, data_manager_1
        )

        # due to the way the tests are run, there may be tasks left lying about,
        # don't rely on there only being one
        assert len(list_response.json) == len(previous_list.json) + 1
        mission_task_present = False
        for task in list_response.json:
            if task['guid'] == mission_task_guid:
                mission_task_present = True
                break
        assert mission_task_present

        # a different data manager should also be able to read the task
        mission_utils.read_mission_task(
            flask_app_client, data_manager_2, mission_task_guid
        )
        mission_utils.read_all_mission_tasks(flask_app_client, data_manager_2)

        # but a regular user should not be able to read the list or the task
        mission_utils.read_mission_task(
            flask_app_client, regular_user, mission_task_guid, 403
        )
        mission_utils.read_all_mission_tasks(flask_app_client, regular_user, 403)

        # delete it
        mission_utils.delete_mission_task(
            flask_app_client, data_manager_1, mission_task_guid
        )
    finally:
        if mission_guid:
            mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)
        for transaction_id in transaction_ids:
            tus_utils.cleanup_tus_dir(transaction_id)


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_set_operation_permission(
    flask_app_client,
    admin_user,
    staff_user,
    regular_user,
    data_manager_1,
    data_manager_2,
    test_root,
):
    from app.modules.missions.models import (
        Mission,
        MissionCollection,
        MissionTask,
    )

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    transaction_ids = []
    transaction_ids.append(transaction_id)
    mission_guid_1, mission_guid_2 = None, None

    try:
        # Mission 1
        response = mission_utils.create_mission(
            flask_app_client,
            data_manager_1,
            mission_utils.make_name('mission')[1],
        )
        mission_guid_1 = response.json['guid']
        temp_mission_1 = Mission.query.get(mission_guid_1)

        previous_list = mission_utils.read_all_mission_collections(
            flask_app_client, data_manager_1
        )

        new_mission_collections_1 = []
        for index in range(3):
            transaction_id = str(random_guid())
            tus_utils.prep_tus_dir(test_root, transaction_id=transaction_id)
            transaction_ids.append(transaction_id)

            nonce, description = mission_utils.make_name('mission collection')
            response = mission_utils.create_mission_collection_with_tus(
                flask_app_client,
                data_manager_1,
                description,
                transaction_id,
                temp_mission_1.guid,
            )
            mission_collection_guid = response.json['guid']
            temp_mission_collection = MissionCollection.query.get(mission_collection_guid)

            new_mission_collections_1.append((nonce, temp_mission_collection))

        current_list = mission_utils.read_all_mission_collections(
            flask_app_client, data_manager_1
        )
        assert len(previous_list.json) + len(new_mission_collections_1) == len(
            current_list.json
        )

        # Mission 2
        response = mission_utils.create_mission(
            flask_app_client,
            data_manager_1,
            mission_utils.make_name('mission')[1],
        )
        mission_guid_2 = response.json['guid']
        temp_mission_2 = Mission.query.get(mission_guid_2)

        previous_list = mission_utils.read_all_mission_collections(
            flask_app_client, data_manager_1
        )

        new_mission_collections_2 = []
        for index in range(3):
            transaction_id = str(random_guid())
            tus_utils.prep_tus_dir(test_root, transaction_id=transaction_id)
            transaction_ids.append(transaction_id)

            nonce, description = mission_utils.make_name('mission collection')
            response = mission_utils.create_mission_collection_with_tus(
                flask_app_client,
                data_manager_1,
                description,
                transaction_id,
                temp_mission_2.guid,
            )
            mission_collection_guid = response.json['guid']
            temp_mission_collection = MissionCollection.query.get(mission_collection_guid)

            new_mission_collections_2.append((nonce, temp_mission_collection))

        current_list = mission_utils.read_all_mission_collections(
            flask_app_client, data_manager_1
        )
        assert len(previous_list.json) + len(new_mission_collections_2) == len(
            current_list.json
        )

        # Make a valid MissionTask
        nonce, new_mission_collection1 = new_mission_collections_1[0]
        nonce, new_mission_collection2 = new_mission_collections_1[1]
        data = [
            utils.set_union_op('search', {}),
            utils.set_difference_op('collections', [str(new_mission_collection1.guid)]),
            utils.set_difference_op(
                'assets', [str(new_mission_collection2.assets[0].guid)]
            ),
        ]

        # Wait for elasticsearch to catch up
        wait_for_elasticsearch_status(flask_app_client, data_manager_1)

        response = mission_utils.create_mission_task(
            flask_app_client, data_manager_1, mission_guid_1, data
        )
        mission_task_guid = response.json['guid']
        mission_task = MissionTask.query.get(mission_task_guid)
        assert mission_task.mission == temp_mission_1

        # Ensure that a MissionTask cannot be created with another Mission's Collections
        nonce, new_mission_collection1 = new_mission_collections_2[0]
        nonce, new_mission_collection2 = new_mission_collections_2[1]
        data = [
            utils.set_union_op('collections', [str(new_mission_collection1.guid)]),
        ]

        response = mission_utils.create_mission_task(
            flask_app_client,
            data_manager_1,
            mission_guid_1,
            data,
            expected_status_code=409,
        )

        # Ensure that a MissionTask cannot be created with another Mission's Assets
        data = [
            utils.set_union_op('assets', [str(new_mission_collection1.assets[0].guid)]),
        ]
        response = mission_utils.create_mission_task(
            flask_app_client,
            data_manager_1,
            mission_guid_1,
            data,
            expected_status_code=409,
        )

        # Ensure that a MissionTask cannot be created with a copy from another Mission's Task
        data = [
            utils.set_union_op('tasks', [str(mission_task.guid)]),
        ]
        response = mission_utils.create_mission_task(
            flask_app_client,
            data_manager_1,
            mission_guid_2,
            data,
            expected_status_code=409,
        )

        # delete it
        mission_utils.delete_mission_task(
            flask_app_client, data_manager_1, mission_task_guid
        )
    finally:
        if mission_guid_1:
            mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid_1)
        if mission_guid_2:
            mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid_2)
        for transaction_id in transaction_ids:
            tus_utils.cleanup_tus_dir(transaction_id)
