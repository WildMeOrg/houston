# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

from tests import utils
import sqlalchemy

import logging


def test_Organization_add_members(db):  # pylint: disable=unused-argument
    from app.modules.organizations.models import (
        Organization,
        OrganizationUserMembershipEnrollment,
    )

    temp_user = utils.generate_user_instance(
        email='temp@localhost', full_name='Temp User'
    )

    temp_org = Organization(
        title='Temp Organization',
        website='temp@temp.org',
    )

    temp_enrollment = OrganizationUserMembershipEnrollment()
    temp_enrollment.user = temp_user
    temp_org.user_membership_enrollments.append(temp_enrollment)

    # Doing this multiple times should not have an effect
    temp_org.user_membership_enrollments.append(temp_enrollment)
    temp_org.user_membership_enrollments.append(temp_enrollment)
    temp_org.user_membership_enrollments.append(temp_enrollment)

    with db.session.begin():
        db.session.add(temp_user)
        db.session.add(temp_org)
        db.session.add(temp_enrollment)

    db.session.refresh(temp_user)
    db.session.refresh(temp_org)
    db.session.refresh(temp_enrollment)

    logging.info(temp_user.organization_membership_enrollments)
    logging.info(temp_org.user_membership_enrollments)

    logging.info(temp_user.memberships)
    logging.info(temp_org.members)

    assert len(temp_user.memberships) == 1
    assert temp_org in temp_user.memberships

    assert len(temp_org.members) == 1
    assert temp_user in temp_org.members

    try:
        duplicate_enrollment = OrganizationUserMembershipEnrollment()
        duplicate_enrollment.user = temp_user
        temp_org.user_membership_enrollments.append(duplicate_enrollment)
        with db.session.begin():
            db.session.add(duplicate_enrollment)
    except (sqlalchemy.orm.exc.FlushError, sqlalchemy.exc.IntegrityError):
        pass

    with db.session.begin():
        db.session.delete(temp_user)
        db.session.delete(temp_org)
        db.session.delete(temp_enrollment)
