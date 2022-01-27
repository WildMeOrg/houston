# -*- coding: utf-8 -*-
import pytest

from tests.utils import module_unavailable, random_nonce
from tests.modules.missions.resources import utils as mission_utils


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_get_mission_task_not_found(flask_app_client):
    response = flask_app_client.get('/api/v1/missions/tasks/wrong-uuid')
    assert response.status_code == 404
    response.close()


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_get_mission_task_by_search(flask_app_client, data_manager_1, test_root):
    from app.modules.missions.models import Mission, MissionTask

    response = mission_utils.create_mission(
        flask_app_client, data_manager_1, 'This is a test mission, please ignore'
    )
    mission_guid = response.json['guid']
    temp_mission = Mission.query.get(mission_guid)
    assert len(temp_mission.tasks) == 0

    previous_list = mission_utils.read_all_mission_tasks(flask_app_client, data_manager_1)

    new_mission_tasks = []
    for index in range(3):
        nonce = random_nonce(8)
        title = 'This is a test task (%s), please ignore' % (nonce,)
        response = mission_utils.create_mission_task(
            flask_app_client, data_manager_1, title, temp_mission.guid
        )
        mission_task_guid = response.json['guid']
        temp_mission_task = MissionTask.query.get(mission_task_guid)

        new_mission_tasks.append((nonce, temp_mission_task))

    current_list = mission_utils.read_all_mission_tasks(flask_app_client, data_manager_1)
    assert len(previous_list.json) + len(new_mission_tasks) == len(current_list.json)

    # Check if the mission is showing the correct number of tasks
    assert len(temp_mission.tasks) == len(new_mission_tasks)

    # Check that the API for a mission's tasks agrees
    response = mission_utils.read_mission_tasks_for_mission(
        flask_app_client, data_manager_1, temp_mission.guid
    )
    assert len(response.json) == 3

    # Search mission tasks by title segment
    nonce, new_mission_task = new_mission_tasks[0]
    current_list = mission_utils.read_all_mission_tasks(
        flask_app_client, data_manager_1, search=nonce
    )
    assert len(current_list.json) == 1
    response = current_list.json[0]
    assert response['title'] == new_mission_task.title

    # Search mission tasks by GUID segment
    nonce, new_mission_task = new_mission_tasks[1]
    guid_str = str(new_mission_task.guid)
    guid_segment = guid_str.split('-')[-1]
    current_list = mission_utils.read_all_mission_tasks(
        flask_app_client, data_manager_1, search=guid_segment
    )
    assert len(current_list.json) == 1
    response = current_list.json[0]
    assert response['title'] == new_mission_task.title

    # Search mission tasks by owner GUID segment
    nonce, new_mission_task = new_mission_tasks[2]
    assert new_mission_task.owner == data_manager_1
    guid_str = str(new_mission_task.owner_guid)
    guid_segment = guid_str.split('-')[-1]
    current_list = mission_utils.read_all_mission_tasks(
        flask_app_client, data_manager_1, search=guid_segment
    )
    assert len(current_list.json) == len(new_mission_tasks)

    # Search mission tasks by mission GUID segment
    nonce, new_mission_task = new_mission_tasks[2]
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
    for nonce, new_mission_task in new_mission_tasks:
        mission_utils.delete_mission_task(
            flask_app_client, data_manager_1, new_mission_task.guid
        )

    # Delete mission
    mission_utils.delete_mission(flask_app_client, data_manager_1, temp_mission.guid)
