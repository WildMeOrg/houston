# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils
from tests.modules.tasks.resources import utils as proj_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('tasks'), reason='Tasks module disabled')
def test_modify_task(db, flask_app_client, admin_user, researcher_1, researcher_2):

    # pylint: disable=invalid-name
    from app.modules.tasks.models import Task

    response = proj_utils.create_task(
        flask_app_client, researcher_1, 'This is a test task, please ignore'
    )
    task_guid = response.json['guid']

    proj = Task.query.get(task_guid)
    assert len(proj.get_members()) == 1

    data = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_add_op('user', '%s' % researcher_2.guid),
    ]
    proj_utils.patch_task(flask_app_client, task_guid, researcher_1, data)
    assert len(proj.get_members()) == 2

    data = [
        utils.patch_test_op(admin_user.password_secret),
        utils.patch_remove_op('user', '%s' % researcher_2.guid),
    ]
    proj_utils.patch_task(flask_app_client, task_guid, admin_user, data, 403)
    assert len(proj.get_members()) == 2

    data = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_remove_op('user', '%s' % researcher_2.guid),
    ]
    proj_utils.patch_task(flask_app_client, task_guid, researcher_1, data)
    assert len(proj.get_members()) == 1

    proj_utils.delete_task(flask_app_client, researcher_1, task_guid)


@pytest.mark.skipif(module_unavailable('tasks'), reason='Tasks module disabled')
def test_owner_permission(flask_app_client, researcher_1, researcher_2):
    response = proj_utils.create_task(
        flask_app_client, researcher_1, 'This is a test task, please ignore'
    )
    task_guid = response.json['guid']

    # another user cannot update the title
    data = [
        utils.patch_test_op(researcher_2.password_secret),
        utils.patch_add_op('title', 'Invalid update'),
    ]
    proj_utils.patch_task(flask_app_client, task_guid, researcher_2, data, 403)

    # Owner can do that
    data = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_add_op('title', 'An owner modified test task, please ignore'),
    ]
    response = proj_utils.patch_task(flask_app_client, task_guid, researcher_1, data)
    assert response.json['title'] == 'An owner modified test task, please ignore'

    # add researcher 2 user to the task
    data = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_add_op('user', '%s' % researcher_2.guid),
    ]
    proj_utils.patch_task(flask_app_client, task_guid, researcher_1, data)

    # make them the owner
    data = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_add_op('owner', '%s' % researcher_2.guid),
    ]
    proj_utils.patch_task(flask_app_client, task_guid, researcher_1, data)

    # try to remove a user as researcher1, no longer owner, should fail
    data = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_remove_op('user', '%s' % researcher_2.guid),
    ]
    proj_utils.patch_task(flask_app_client, task_guid, researcher_1, data, 409)

    # TODO: This returns a 200, due to the default of True in PatchJSONParameters:perform_patch

    # response = proj_utils.patch_task(
    #     flask_app_client,
    #     task_guid,
    #     temp_user,
    #     {'title': 'This is an owner modified test task, please ignore'},
    # )
    # utils.validate_dict_response(response, 200, {'guid', 'title'})
    # # It does at least fail to do anything
    # assert response.json['title'] == 'This is an admin modified test task, please ignore'
