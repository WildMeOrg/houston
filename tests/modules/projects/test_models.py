# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

from tests import utils
import sqlalchemy

import logging


def test_Project_add_members(db):  # pylint: disable=unused-argument
    from app.modules.projects.models import (
        Project,
        ProjectUserMembershipEnrollment,
    )

    temp_user = utils.generate_user_instance(
        email='temp@localhost', full_name='Temp User'
    )

    temp_proj = Project(
        title='Temp Project',
    )

    temp_enrollment = ProjectUserMembershipEnrollment()
    temp_enrollment.user = temp_user
    temp_proj.user_membership_enrollments.append(temp_enrollment)

    # Doing this multiple times should not have an effect
    temp_proj.user_membership_enrollments.append(temp_enrollment)
    temp_proj.user_membership_enrollments.append(temp_enrollment)
    temp_proj.user_membership_enrollments.append(temp_enrollment)

    with db.session.begin():
        db.session.add(temp_user)
        db.session.add(temp_proj)
        db.session.add(temp_enrollment)

    db.session.refresh(temp_user)
    db.session.refresh(temp_proj)
    db.session.refresh(temp_enrollment)

    logging.info(temp_user.project_membership_enrollments)
    logging.info(temp_proj.user_membership_enrollments)

    logging.info(temp_user.projects)
    logging.info(temp_proj.members)

    assert len(temp_user.projects) == 1
    assert temp_proj in temp_user.projects

    assert len(temp_proj.members) == 1
    assert temp_user in temp_proj.members

    try:
        duplicate_enrollment = ProjectUserMembershipEnrollment()
        duplicate_enrollment.user = temp_user
        temp_proj.user_membership_enrollments.append(duplicate_enrollment)
        with db.session.begin():
            db.session.add(duplicate_enrollment)
    except (sqlalchemy.orm.exc.FlushError, sqlalchemy.exc.IntegrityError):
        pass

    with db.session.begin():
        db.session.delete(temp_user)
        db.session.delete(temp_proj)
        db.session.delete(temp_enrollment)
