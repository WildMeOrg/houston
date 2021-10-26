# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import sqlalchemy

import logging


def test_mission_add_members(
    db, temp_user, researcher_1, researcher_2
):  # pylint: disable=unused-argument
    from app.modules.missions.models import (
        Mission,
        MissionUserMembershipEnrollment,
    )

    temp_proj = Mission(
        title='Temp Mission',
        owner_guid=temp_user.guid,
    )

    temp_enrollment = MissionUserMembershipEnrollment()
    temp_enrollment.user = temp_user
    temp_proj.user_membership_enrollments.append(temp_enrollment)

    # Doing this multiple times should not have an effect
    temp_proj.user_membership_enrollments.append(temp_enrollment)
    temp_proj.user_membership_enrollments.append(temp_enrollment)
    temp_proj.user_membership_enrollments.append(temp_enrollment)

    with db.session.begin():
        db.session.add(temp_proj)
        db.session.add(temp_enrollment)

    db.session.refresh(temp_user)
    db.session.refresh(temp_proj)
    db.session.refresh(temp_enrollment)

    for value in temp_proj.user_membership_enrollments:
        assert value in temp_user.mission_membership_enrollments
    logging.info(temp_user.mission_membership_enrollments)
    logging.info(temp_proj.user_membership_enrollments)

    logging.info(temp_user.get_missions())
    logging.info(temp_proj)

    assert len(temp_user.get_missions()) >= 1
    assert temp_proj in temp_user.get_missions()

    assert len(temp_proj.get_members()) == 1
    assert temp_user in temp_proj.get_members()

    try:
        duplicate_enrollment = MissionUserMembershipEnrollment()
        duplicate_enrollment.user = temp_user
        temp_proj.user_membership_enrollments.append(duplicate_enrollment)
        with db.session.begin():
            db.session.add(duplicate_enrollment)
    except (sqlalchemy.orm.exc.FlushError, sqlalchemy.exc.IntegrityError):
        pass

    temp_proj.add_user_in_context(researcher_1)
    # try removing a user that's not in the mission
    temp_proj.remove_user_in_context(researcher_2)
    temp_proj.remove_user_in_context(researcher_1)

    with db.session.begin():
        db.session.delete(temp_proj)
        db.session.delete(temp_enrollment)
