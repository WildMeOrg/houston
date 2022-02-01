# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.missions.resources import utils as mission_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_create_and_delete_mission_task(flask_app_client, data_manager_1):
    # pylint: disable=invalid-name
    from app.modules.missions.models import (
        MissionTask,
        MissionTaskUserAssignment,
        MissionTaskAssetParticipation,
    )

    response = mission_utils.create_mission(
        flask_app_client, data_manager_1, 'This is a test mission, please ignore'
    )
    mission_guid = response.json['guid']

    response = mission_utils.create_mission_task(
        flask_app_client,
        data_manager_1,
        'This is a test task, please ignore',
        mission_guid,
    )

    mission_task_guid = response.json['guid']
    read_mission_task = MissionTask.query.get(response.json['guid'])
    assert read_mission_task.title == 'This is a test task, please ignore'
    assert read_mission_task.owner == data_manager_1

    # Try reading it back
    mission_utils.read_mission_task(flask_app_client, data_manager_1, mission_task_guid)

    # And deleting it
    mission_utils.delete_mission_task(flask_app_client, data_manager_1, mission_task_guid)

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

    mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_mission_task_permission(
    flask_app_client, admin_user, staff_user, regular_user, data_manager_1, data_manager_2
):
    # Before we create any MissionTasks, find out how many are there already
    previous_list = mission_utils.read_all_mission_tasks(flask_app_client, staff_user)

    response = mission_utils.create_mission(
        flask_app_client, data_manager_1, 'This is a test mission, please ignore'
    )
    mission_guid = response.json['guid']

    response = mission_utils.create_mission_task(
        flask_app_client,
        data_manager_1,
        'This is a test task, please ignore',
        mission_guid,
    )

    mission_task_guid = response.json['guid']

    # staff user should be able to read anything
    mission_utils.read_mission_task(flask_app_client, staff_user, mission_task_guid)
    mission_utils.read_all_mission_tasks(flask_app_client, staff_user)

    # admin user should be able to read any tasks as well
    mission_utils.read_mission_task(flask_app_client, admin_user, mission_task_guid)
    mission_utils.read_all_mission_tasks(flask_app_client, admin_user)

    # user that created task can read it back plus the list
    mission_utils.read_mission_task(flask_app_client, data_manager_1, mission_task_guid)
    list_response = mission_utils.read_all_mission_tasks(flask_app_client, data_manager_1)

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
    mission_utils.read_mission_task(flask_app_client, data_manager_2, mission_task_guid)
    mission_utils.read_all_mission_tasks(flask_app_client, data_manager_2)

    # but a regular user should not be able to read the list or the task
    mission_utils.read_mission_task(
        flask_app_client, regular_user, mission_task_guid, 403
    )
    mission_utils.read_all_mission_tasks(flask_app_client, regular_user, 403)

    # delete it
    mission_utils.delete_mission_task(flask_app_client, data_manager_1, mission_task_guid)

    mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)
