# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import sqlalchemy

import logging


def test_task_add_members(
    db, temp_user, researcher_1, researcher_2
):  # pylint: disable=unused-argument
    from app.modules.tasks.models import (
        Task,
        TaskUserAssignment,
    )

    temp_proj = Task(
        title='Temp Task',
        owner_guid=temp_user.guid,
    )

    temp_assignment = TaskUserAssignment()
    temp_assignment.user = temp_user
    temp_proj.user_assignments.append(temp_assignment)

    # Doing this multiple times should not have an effect
    temp_proj.user_assignments.append(temp_assignment)
    temp_proj.user_assignments.append(temp_assignment)
    temp_proj.user_assignments.append(temp_assignment)

    with db.session.begin():
        db.session.add(temp_proj)
        db.session.add(temp_assignment)

    db.session.refresh(temp_user)
    db.session.refresh(temp_proj)
    db.session.refresh(temp_assignment)

    for value in temp_proj.user_assignments:
        assert value in temp_user.task_assignments
    logging.info(temp_user.task_assignments)
    logging.info(temp_proj.user_assignments)

    logging.info(temp_user.get_tasks())
    logging.info(temp_proj)

    assert len(temp_user.get_tasks()) >= 1
    assert temp_proj in temp_user.get_tasks()

    assert len(temp_proj.get_assigned_users()) == 1
    assert temp_user in temp_proj.get_assigned_users()

    try:
        duplicate_assignment = TaskUserAssignment()
        duplicate_assignment.user = temp_user
        temp_proj.user_assignments.append(duplicate_assignment)
        with db.session.begin():
            db.session.add(duplicate_assignment)
    except (sqlalchemy.orm.exc.FlushError, sqlalchemy.exc.IntegrityError):
        pass

    temp_proj.add_user_in_context(researcher_1)
    # try removing a user that's not in the task
    temp_proj.remove_user_in_context(researcher_2)
    temp_proj.remove_user_in_context(researcher_1)

    with db.session.begin():
        db.session.delete(temp_proj)
        db.session.delete(temp_assignment)
