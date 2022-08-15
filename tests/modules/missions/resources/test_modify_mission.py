# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

import pytest

from tests import utils
from tests.modules.missions.resources import utils as mission_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_modify_mission_users(db, flask_app_client, admin_user, admin_user_2):

    # pylint: disable=invalid-name
    from app.modules.missions.models import Mission

    response = mission_utils.create_mission(
        flask_app_client,
        admin_user,
        mission_utils.make_name('mission')[1],
    )
    mission_guid = response.json['guid']

    mission = Mission.query.get(mission_guid)
    assert len(mission.get_members()) == 1

    data = [
        utils.patch_test_op(admin_user.password_secret),
        utils.patch_add_op('user', '%s' % admin_user_2.guid),
    ]
    mission_utils.patch_mission(flask_app_client, mission_guid, admin_user, data)
    assert len(mission.get_members()) == 2

    data = [
        utils.patch_test_op(admin_user.password_secret),
        utils.patch_remove_op('user', '%s' % admin_user_2.guid),
    ]
    mission_utils.patch_mission(flask_app_client, mission_guid, admin_user, data)
    assert len(mission.get_members()) == 1

    mission_utils.delete_mission(flask_app_client, admin_user, mission_guid)


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_owner_permission(flask_app_client, admin_user, admin_user_2):

    response = mission_utils.create_mission(
        flask_app_client,
        admin_user,
        mission_utils.make_name('mission')[1],
    )
    mission_guid = response.json['guid']

    # Patch the mission's title
    data = [
        utils.patch_replace_op('title', 'An owner modified test mission, please ignore'),
        utils.patch_replace_op('notes', 'An owner modified test mission, please ignore'),
    ]
    response = mission_utils.patch_mission(
        flask_app_client, mission_guid, admin_user, data
    )
    assert response.json['title'] == 'An owner modified test mission, please ignore'
    assert response.json['notes'] == 'An owner modified test mission, please ignore'

    # add data manager 2 user to the mission
    data = [
        utils.patch_test_op(admin_user.password_secret),
        utils.patch_add_op('user', '%s' % admin_user_2.guid),
    ]
    mission_utils.patch_mission(flask_app_client, mission_guid, admin_user, data)

    # make them the owner
    data = [
        utils.patch_test_op(admin_user.password_secret),
        utils.patch_replace_op('owner', '%s' % admin_user_2.guid),
    ]
    mission_utils.patch_mission(flask_app_client, mission_guid, admin_user, data)

    # try to remove a user as data manager 1, no longer owner, should fail
    data = [
        utils.patch_test_op(admin_user.password_secret),
        utils.patch_remove_op('user', '%s' % admin_user_2.guid),
    ]
    mission_utils.patch_mission(flask_app_client, mission_guid, admin_user, data, 409)

    mission_utils.delete_mission(flask_app_client, admin_user, mission_guid)
