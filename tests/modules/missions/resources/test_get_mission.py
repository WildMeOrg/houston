# -*- coding: utf-8 -*-
import pytest

from tests.utils import module_unavailable, random_nonce
from tests.modules.missions.resources import utils as mission_utils


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_get_mission_not_found(flask_app_client):
    response = flask_app_client.get('/api/v1/missions/wrong-uuid')
    assert response.status_code == 404
    response.close()


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_get_owned_missions(flask_app_client, admin_user, data_manager_1, data_manager_2):
    from app.modules.missions.models import Mission

    previous_list = mission_utils.read_all_missions(flask_app_client, data_manager_1)

    new_missions = []
    for owner in [data_manager_1, data_manager_2]:
        for index in range(3):
            nonce = random_nonce(8)
            title = 'This is a test mission (%s), please ignore' % (nonce,)
            response = mission_utils.create_mission(flask_app_client, owner, title)
            mission_guid = response.json['guid']
            mission = Mission.query.get(mission_guid)
            new_missions.append((nonce, mission))

    # Data managers can see other data managers' missions
    current_list = mission_utils.read_all_missions(flask_app_client, data_manager_1)
    assert len(previous_list.json) + len(new_missions) == len(current_list.json)

    # Get data manager 1's assigned missions
    data_manager1_list = mission_utils.read_user_assigned_missions(
        flask_app_client, data_manager_1
    )
    guid1_list = [mission['guid'] for mission in data_manager1_list.json]

    data_manager2_list = mission_utils.read_user_assigned_missions(
        flask_app_client, data_manager_2
    )
    guid2_list = [mission['guid'] for mission in data_manager2_list.json]

    assert len(set(guid1_list) & set(guid2_list)) == 0

    # Check my assignments when logged in
    me_data_manager1_list = mission_utils.read_user_assigned_missions(
        flask_app_client, data_manager_1, user_guid='me'
    )
    me_data_manager2_list = mission_utils.read_user_assigned_missions(
        flask_app_client, data_manager_2, user_guid='me'
    )
    assert data_manager1_list.json == me_data_manager1_list.json
    assert data_manager2_list.json == me_data_manager2_list.json

    # logged in as data_manager_1, we should not be able to retrieve data_manager_2's missions on their behalf
    mission_utils.read_user_assigned_missions(
        flask_app_client,
        data_manager_1,
        user_guid=data_manager_2.guid,
        expected_status_code=403,
    )

    # logged in as admin_user, however, we should be able to retrieve data_manager_2's missions on their behalf
    admin_data_manager2_list = mission_utils.read_user_assigned_missions(
        flask_app_client, admin_user, user_guid=data_manager_2.guid
    )
    assert data_manager2_list.json == admin_data_manager2_list.json

    # Delete missions
    for nonce, new_mission in new_missions:
        mission_utils.delete_mission(flask_app_client, data_manager_1, new_mission.guid)


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_get_mission_by_search(flask_app_client, data_manager_1):
    from app.modules.missions.models import Mission

    previous_list = mission_utils.read_all_missions(flask_app_client, data_manager_1)

    new_missions = []
    for index in range(3):
        nonce = random_nonce(8)
        title = 'This is a test mission (%s), please ignore' % (nonce,)
        response = mission_utils.create_mission(flask_app_client, data_manager_1, title)
        mission_guid = response.json['guid']
        mission = Mission.query.get(mission_guid)
        new_missions.append((nonce, mission))

    current_list = mission_utils.read_all_missions(flask_app_client, data_manager_1)
    assert len(previous_list.json) + len(new_missions) == len(current_list.json)

    # Search missions by title segment
    nonce, new_mission = new_missions[0]
    current_list = mission_utils.read_all_missions(
        flask_app_client, data_manager_1, search=nonce
    )
    assert len(current_list.json) == 1
    response = current_list.json[0]
    assert response['title'] == new_mission.title

    # Search missions by GUID segment
    nonce, new_mission = new_missions[1]
    guid_str = str(new_mission.guid)
    guid_segment = guid_str.split('-')[-1]
    current_list = mission_utils.read_all_missions(
        flask_app_client, data_manager_1, search=guid_segment
    )
    assert len(current_list.json) == 1
    response = current_list.json[0]
    assert response['title'] == new_mission.title

    # Search missions by owner GUID segment
    nonce, new_mission = new_missions[2]
    guid_str = str(new_mission.owner_guid)
    guid_segment = guid_str.split('-')[-1]
    current_list = mission_utils.read_all_missions(
        flask_app_client, data_manager_1, search=guid_segment
    )
    assert len(current_list.json) == len(new_missions)

    # Limit responses
    limited_list = mission_utils.read_all_missions(
        flask_app_client, data_manager_1, search=guid_segment, limit=2
    )
    assert len(current_list.json[:2]) == len(limited_list.json)

    # Limit responses (with offset)
    limited_list = mission_utils.read_all_missions(
        flask_app_client, data_manager_1, search=guid_segment, offset=1, limit=2
    )
    assert len(current_list.json[1:3]) == len(limited_list.json)

    # Delete missions
    for nonce, new_mission in new_missions:
        mission_utils.delete_mission(flask_app_client, data_manager_1, new_mission.guid)
