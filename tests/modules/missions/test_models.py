# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import sqlalchemy

import logging


def test_mission_add_members(
    db, temp_user, researcher_1, researcher_2
):  # pylint: disable=unused-argument
    from app.modules.missions.models import (
        Mission,
        MissionUserAssignment,
    )

    temp_mission = Mission(
        title='Temp Mission',
        owner_guid=temp_user.guid,
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

    logging.info(temp_user.get_missions())
    logging.info(temp_mission)

    assert len(temp_user.get_missions()) >= 1
    assert temp_mission in temp_user.get_missions()

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

    temp_mission.add_user_in_context(researcher_1)
    # try removing a user that's not in the mission
    temp_mission.remove_user_in_context(researcher_2)
    temp_mission.remove_user_in_context(researcher_1)

    with db.session.begin():
        db.session.delete(temp_mission)
        db.session.delete(temp_assignment)
