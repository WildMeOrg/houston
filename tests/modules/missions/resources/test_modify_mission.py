# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils
from tests.modules.missions.resources import utils as mission_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_modify_mission_users(db, flask_app_client, data_manager_1, data_manager_2):

    # pylint: disable=invalid-name
    from app.modules.missions.models import Mission

    response = mission_utils.create_mission(
        flask_app_client, data_manager_1, 'This is a test mission, please ignore'
    )
    mission_guid = response.json['guid']

    mission = Mission.query.get(mission_guid)
    assert len(mission.get_members()) == 1

    data = [
        utils.patch_test_op(data_manager_1.password_secret),
        utils.patch_add_op('user', '%s' % data_manager_2.guid),
    ]
    mission_utils.patch_mission(flask_app_client, mission_guid, data_manager_1, data)
    assert len(mission.get_members()) == 2

    data = [
        utils.patch_test_op(data_manager_1.password_secret),
        utils.patch_remove_op('user', '%s' % data_manager_2.guid),
    ]
    mission_utils.patch_mission(flask_app_client, mission_guid, data_manager_1, data)
    assert len(mission.get_members()) == 1

    mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_owner_permission(flask_app_client, data_manager_1, data_manager_2):

    response = mission_utils.create_mission(
        flask_app_client, data_manager_1, 'This is a test mission, please ignore'
    )
    mission_guid = response.json['guid']

    # Patch the mission's title
    data = [
        utils.patch_replace_op('title', 'An owner modified test mission, please ignore'),
        utils.patch_replace_op('notes', 'An owner modified test mission, please ignore'),
    ]
    response = mission_utils.patch_mission(
        flask_app_client, mission_guid, data_manager_1, data
    )
    assert response.json['title'] == 'An owner modified test mission, please ignore'
    assert response.json['notes'] == 'An owner modified test mission, please ignore'

    # add data manager 2 user to the mission
    data = [
        utils.patch_test_op(data_manager_1.password_secret),
        utils.patch_add_op('user', '%s' % data_manager_2.guid),
    ]
    mission_utils.patch_mission(flask_app_client, mission_guid, data_manager_1, data)

    # make them the owner
    data = [
        utils.patch_test_op(data_manager_1.password_secret),
        utils.patch_replace_op('owner', '%s' % data_manager_2.guid),
    ]
    mission_utils.patch_mission(flask_app_client, mission_guid, data_manager_1, data)

    # try to remove a user as data manager 1, no longer owner, should fail
    data = [
        utils.patch_test_op(data_manager_1.password_secret),
        utils.patch_remove_op('user', '%s' % data_manager_2.guid),
    ]
    mission_utils.patch_mission(flask_app_client, mission_guid, data_manager_1, data, 409)

    mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)
