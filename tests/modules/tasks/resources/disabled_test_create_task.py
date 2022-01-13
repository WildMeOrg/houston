# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.tasks.resources import utils as proj_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('tasks'), reason='Tasks module disabled')
def test_create_and_delete_task(flask_app_client, researcher_1):
    # pylint: disable=invalid-name
    from app.modules.tasks.models import Task

    response = proj_utils.create_task(
        flask_app_client, researcher_1, 'This is a test task, please ignore'
    )

    task_guid = response.json['guid']
    read_task = Task.query.get(response.json['guid'])
    assert read_task.title == 'This is a test task, please ignore'
    assert read_task.owner == researcher_1

    # Try reading it back
    proj_utils.read_task(flask_app_client, researcher_1, task_guid)

    # And deleting it
    proj_utils.delete_task(flask_app_client, researcher_1, task_guid)

    read_task = Task.query.get(task_guid)
    assert read_task is None


@pytest.mark.skipif(module_unavailable('tasks'), reason='Tasks module disabled')
def test_task_permission(
    flask_app_client, admin_user, staff_user, researcher_1, researcher_2
):
    # Before we create any Tasks, find out how many are there already
    previous_list = proj_utils.read_all_tasks(flask_app_client, staff_user)

    response = proj_utils.create_task(
        flask_app_client, researcher_1, 'This is a test task, please ignore'
    )

    task_guid = response.json['guid']

    # staff user should be able to read anything
    proj_utils.read_task(flask_app_client, staff_user, task_guid)
    proj_utils.read_all_tasks(flask_app_client, staff_user)

    # admin user should not be able to read any tasks
    proj_utils.read_task(flask_app_client, admin_user, task_guid, 403)
    proj_utils.read_all_tasks(flask_app_client, admin_user, 403)

    # user that created task can read it back plus the list
    proj_utils.read_task(flask_app_client, researcher_1, task_guid)
    list_response = proj_utils.read_all_tasks(flask_app_client, researcher_1)

    # due to the way the tests are run, there may be tasks left lying about,
    # don't rely on there only being one
    assert len(list_response.json) == len(previous_list.json) + 1
    task_present = False
    for task in list_response.json:
        if task['guid'] == task_guid:
            task_present = True
            break
    assert task_present

    # but a different researcher can read the list but not the task
    proj_utils.read_task(flask_app_client, researcher_2, task_guid, 403)
    proj_utils.read_all_tasks(flask_app_client, researcher_2)

    # delete it
    proj_utils.delete_task(flask_app_client, researcher_1, task_guid)
