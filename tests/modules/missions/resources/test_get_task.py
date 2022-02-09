# -*- coding: utf-8 -*-
import pytest

from tests import utils
from tests.utils import module_unavailable, random_nonce, random_guid
from tests.modules.missions.resources import utils as mission_utils
import tests.extensions.tus.utils as tus_utils


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_get_mission_task_not_found(flask_app_client):
    response = flask_app_client.get('/api/v1/missions/tasks/wrong-uuid')
    assert response.status_code == 404
    response.close()


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_get_mission_task_by_search(flask_app_client, data_manager_1, test_root):
    from app.modules.missions.models import (
        Mission,
        MissionCollection,
        MissionTask,
    )

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    transaction_ids = []
    transaction_ids.append(transaction_id)
    mission_guid = None

    try:
        response = mission_utils.create_mission(
            flask_app_client, data_manager_1, 'This is a test mission, please ignore'
        )
        mission_guid = response.json['guid']
        temp_mission = Mission.query.get(mission_guid)

        previous_list = mission_utils.read_all_mission_collections(
            flask_app_client, data_manager_1
        )

        previous_list = mission_utils.read_all_mission_tasks(
            flask_app_client, data_manager_1
        )

        new_mission_collections = []
        for index in range(3):
            transaction_id = str(random_guid())
            tus_utils.prep_tus_dir(test_root, transaction_id=transaction_id)
            transaction_ids.append(transaction_id)

            nonce = random_nonce(8)
            description = 'This is a test mission collection (%s), please ignore' % (
                nonce,
            )
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
            utils.set_union_op('search', 'does-not-work'),
            utils.set_difference_op('collections', [str(new_mission_collection1.guid)]),
            utils.set_difference_op(
                'assets', [str(new_mission_collection2.assets[0].guid)]
            ),
        ]

        new_mission_tasks = []
        for index in range(3):
            response = mission_utils.create_mission_task(
                flask_app_client, data_manager_1, mission_guid, data
            )
            mission_task_guid = response.json['guid']
            temp_mission_task = MissionTask.query.get(mission_task_guid)

            new_mission_tasks.append(temp_mission_task)

        current_list = mission_utils.read_all_mission_tasks(
            flask_app_client, data_manager_1
        )
        assert len(previous_list.json) + len(new_mission_tasks) == len(current_list.json)

        # Check if the mission is showing the correct number of tasks
        assert len(temp_mission.tasks) == len(new_mission_tasks)

        # Check that the API for a mission's tasks agrees
        response = mission_utils.read_mission_tasks_for_mission(
            flask_app_client, data_manager_1, temp_mission.guid
        )
        assert len(response.json) == 3

        # Search mission tasks by GUID segment
        new_mission_task = new_mission_tasks[1]
        guid_str = str(new_mission_task.guid)
        guid_segment = guid_str.split('-')[-1]
        current_list = mission_utils.read_all_mission_tasks(
            flask_app_client, data_manager_1, search=guid_segment
        )
        assert len(current_list.json) == 1
        response = current_list.json[0]
        assert response['title'] == new_mission_task.title

        # Search mission tasks by owner GUID segment
        new_mission_task = new_mission_tasks[2]
        assert new_mission_task.owner == data_manager_1
        guid_str = str(new_mission_task.owner_guid)
        guid_segment = guid_str.split('-')[-1]
        current_list = mission_utils.read_all_mission_tasks(
            flask_app_client, data_manager_1, search=guid_segment
        )
        assert len(current_list.json) == len(new_mission_tasks)

        # Search mission tasks by mission GUID segment
        new_mission_task = new_mission_tasks[2]
        assert new_mission_task.mission == temp_mission
        guid_str = str(new_mission_task.mission_guid)
        guid_segment = guid_str.split('-')[-1]
        current_list = mission_utils.read_all_mission_tasks(
            flask_app_client, data_manager_1, search=guid_segment
        )
        assert len(current_list.json) == len(new_mission_tasks)

        # Limit responses
        limited_list = mission_utils.read_all_mission_tasks(
            flask_app_client, data_manager_1, search=guid_segment, limit=2
        )
        assert len(current_list.json[:2]) == len(limited_list.json)

        # Limit responses (with offset)
        limited_list = mission_utils.read_all_mission_tasks(
            flask_app_client, data_manager_1, search=guid_segment, offset=1, limit=2
        )
        assert len(current_list.json[1:3]) == len(limited_list.json)

        # Delete mission tasks
        for new_mission_task in new_mission_tasks:
            mission_utils.delete_mission_task(
                flask_app_client, data_manager_1, new_mission_task.guid
            )
    finally:
        if mission_guid:
            mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)

        for transaction_id in transaction_ids:
            tus_utils.cleanup_tus_dir(transaction_id)
