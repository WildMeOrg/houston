# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging

import pytest
import sqlalchemy

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_mission_add_members(
    db, temp_user, admin_user, admin_user_2
):  # pylint: disable=unused-argument
    from app.modules.missions.models import Mission, MissionUserAssignment

    temp_mission = Mission(
        title='Temp Mission',
        owner=temp_user,
    )

    temp_assignment = MissionUserAssignment()
    temp_assignment.user = temp_user
    temp_mission.user_assignments.append(temp_assignment)

    # Doing this multiple times should not have an effect
    temp_mission.user_assignments.append(temp_assignment)
    temp_mission.user_assignments.append(temp_assignment)
    temp_mission.user_assignments.append(temp_assignment)

    with db.session.begin():
        db.session.add(temp_mission)
        db.session.add(temp_assignment)

    db.session.refresh(temp_user)
    db.session.refresh(temp_mission)
    db.session.refresh(temp_assignment)

    for value in temp_mission.user_assignments:
        assert value in temp_user.mission_assignments
    logging.info(temp_user.mission_assignments)
    logging.info(temp_mission.user_assignments)

    logging.info(temp_user.get_assigned_missions())
    logging.info(temp_mission)

    assert len(temp_user.get_assigned_missions()) >= 1
    assert temp_mission in temp_user.get_assigned_missions()

    assert len(temp_mission.get_members()) == 1
    assert temp_user in temp_mission.get_members()

    try:
        duplicate_assignment = MissionUserAssignment()
        duplicate_assignment.user = temp_user
        temp_mission.user_assignments.append(duplicate_assignment)
        with db.session.begin():
            db.session.add(duplicate_assignment)
    except (sqlalchemy.orm.exc.FlushError, sqlalchemy.exc.IntegrityError):
        pass

    temp_mission.add_user_in_context(admin_user)
    # try removing a user that's not in the mission
    temp_mission.remove_user_in_context(admin_user_2)
    temp_mission.remove_user_in_context(admin_user)

    with db.session.begin():
        db.session.delete(temp_mission)
        db.session.delete(temp_assignment)


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_mission_task_add_members(
    db, temp_user, admin_user, admin_user_2
):  # pylint: disable=unused-argument
    from app.modules.missions.models import (
        Mission,
        MissionTask,
        MissionTaskUserAssignment,
    )

    temp_mission = Mission(
        title='Temp Mission',
        owner=temp_user,
    )

    temp_mission_task = MissionTask(
        title='Temp MissionTask',
        owner=temp_user,
        mission=temp_mission,
    )

    temp_assignment = MissionTaskUserAssignment()
    temp_assignment.user = temp_user
    temp_assignment.assigner = admin_user
    temp_mission_task.user_assignments.append(temp_assignment)

    # Doing this multiple times should not have an effect
    temp_mission_task.user_assignments.append(temp_assignment)
    temp_mission_task.user_assignments.append(temp_assignment)
    temp_mission_task.user_assignments.append(temp_assignment)

    with db.session.begin():
        db.session.add(temp_mission_task)
        db.session.add(temp_assignment)

    db.session.refresh(temp_user)
    db.session.refresh(temp_mission_task)
    db.session.refresh(temp_assignment)

    for value in temp_mission_task.user_assignments:
        assert value in temp_user.mission_task_assignments
    logging.info(temp_user.mission_task_assignments)
    logging.info(temp_mission_task.user_assignments)

    logging.info(temp_user.get_assigned_mission_tasks())
    logging.info(temp_mission_task)

    assert len(temp_user.get_assigned_mission_tasks()) >= 1
    assert temp_mission_task in temp_user.get_assigned_mission_tasks()

    assert len(temp_mission_task.get_assigned_users()) == 1
    assert temp_user in temp_mission_task.get_assigned_users()

    try:
        duplicate_assignment = MissionTaskUserAssignment()
        duplicate_assignment.user = temp_user
        duplicate_assignment.assigner = admin_user
        temp_mission_task.user_assignments.append(duplicate_assignment)
        with db.session.begin():
            db.session.add(duplicate_assignment)
    except (sqlalchemy.orm.exc.FlushError, sqlalchemy.exc.IntegrityError):
        pass

    temp_mission_task.add_user_in_context(admin_user, admin_user)
    # try removing a user that's not in the task
    temp_mission_task.remove_user_in_context(admin_user_2)
    temp_mission_task.remove_user_in_context(admin_user)

    with db.session.begin():
        db.session.delete(temp_assignment)
        db.session.delete(temp_mission_task)
        db.session.delete(temp_mission)
