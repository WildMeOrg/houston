# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.missions.resources import utils as mission_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_create_and_delete_mission(flask_app_client, data_manager_1):
    # pylint: disable=invalid-name
    from app.modules.missions.models import (
        Mission,
        MissionUserAssignment,
    )

    response = mission_utils.create_mission(
        flask_app_client, data_manager_1, 'This is a test mission, please ignore'
    )

    mission_guid = response.json['guid']
    read_mission = Mission.query.get(response.json['guid'])
    assert read_mission.title == 'This is a test mission, please ignore'
    assert read_mission.owner == data_manager_1

    # Try reading it back
    mission_utils.read_mission(flask_app_client, data_manager_1, mission_guid)

    # And deleting it
    mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)

    read_mission = Mission.query.get(mission_guid)
    assert read_mission is None

    read_mission = MissionUserAssignment.query.filter_by(mission_guid=mission_guid).all()
    assert len(read_mission) == 0


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_mission_permission(
    flask_app_client, admin_user, staff_user, regular_user, data_manager_1, data_manager_2
):
    # Before we create any Missions, find out how many are there already
    previous_list = mission_utils.read_all_missions(flask_app_client, staff_user)

    response = mission_utils.create_mission(
        flask_app_client, data_manager_1, 'This is a test mission, please ignore'
    )

    mission_guid = response.json['guid']

    # staff user should be able to read anything
    mission_utils.read_mission(flask_app_client, staff_user, mission_guid)
    mission_utils.read_all_missions(flask_app_client, staff_user)

    # admin user should be able to read any missions as well
    mission_utils.read_mission(flask_app_client, admin_user, mission_guid)
    mission_utils.read_all_missions(flask_app_client, admin_user)

    # user that created mission can read it back plus the list
    mission_utils.read_mission(flask_app_client, data_manager_1, mission_guid)
    list_response = mission_utils.read_all_missions(flask_app_client, data_manager_1)

    # due to the way the tests are run, there may be missions left lying about,
    # don't rely on there only being one
    assert len(list_response.json) == len(previous_list.json) + 1
    mission_present = False
    for mission in list_response.json:
        if mission['guid'] == mission_guid:
            mission_present = True
            break
    assert mission_present

    # a different data manager should also be able to read the mission
    mission_utils.read_mission(flask_app_client, data_manager_2, mission_guid)
    mission_utils.read_all_missions(flask_app_client, data_manager_2)

    # but a regular user should not be able to read the list or the mission
    mission_utils.read_mission(flask_app_client, regular_user, mission_guid, 403)
    mission_utils.read_all_missions(flask_app_client, regular_user, 403)

    # delete it
    mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)
