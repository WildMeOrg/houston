# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.missions.resources import utils as proj_utils


def test_create_and_delete_mission(flask_app_client, researcher_1):
    # pylint: disable=invalid-name
    from app.modules.missions.models import Mission

    response = proj_utils.create_mission(
        flask_app_client, researcher_1, 'This is a test mission, please ignore'
    )

    mission_guid = response.json['guid']
    read_mission = Mission.query.get(response.json['guid'])
    assert read_mission.title == 'This is a test mission, please ignore'
    assert read_mission.owner == researcher_1

    # Try reading it back
    proj_utils.read_mission(flask_app_client, researcher_1, mission_guid)

    # And deleting it
    proj_utils.delete_mission(flask_app_client, researcher_1, mission_guid)

    read_mission = Mission.query.get(mission_guid)
    assert read_mission is None


def test_mission_permission(
    flask_app_client, admin_user, staff_user, researcher_1, researcher_2
):
    # Before we create any Missions, find out how many are there already
    previous_list = proj_utils.read_all_missions(flask_app_client, staff_user)

    response = proj_utils.create_mission(
        flask_app_client, researcher_1, 'This is a test mission, please ignore'
    )

    mission_guid = response.json['guid']

    # staff user should be able to read anything
    proj_utils.read_mission(flask_app_client, staff_user, mission_guid)
    proj_utils.read_all_missions(flask_app_client, staff_user)

    # admin user should not be able to read any missions
    proj_utils.read_mission(flask_app_client, admin_user, mission_guid, 403)
    proj_utils.read_all_missions(flask_app_client, admin_user, 403)

    # user that created mission can read it back plus the list
    proj_utils.read_mission(flask_app_client, researcher_1, mission_guid)
    list_response = proj_utils.read_all_missions(flask_app_client, researcher_1)

    # due to the way the tests are run, there may be missions left lying about,
    # don't rely on there only being one
    assert len(list_response.json) == len(previous_list.json) + 1
    mission_present = False
    for mission in list_response.json:
        if mission['guid'] == mission_guid:
            mission_present = True
            break
    assert mission_present

    # but a different researcher can read the list but not the mission
    proj_utils.read_mission(flask_app_client, researcher_2, mission_guid, 403)
    proj_utils.read_all_missions(flask_app_client, researcher_2)

    # delete it
    proj_utils.delete_mission(flask_app_client, researcher_1, mission_guid)
