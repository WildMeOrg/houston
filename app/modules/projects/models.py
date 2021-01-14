# -*- coding: utf-8 -*-
"""
Projects database models
--------------------
"""

from sqlalchemy_utils import Timestamp
from app.extensions import db, HoustonModel
from app.modules.encounters import models as encounters_models  # NOQA
import uuid


# All many:many associations handled as Houston model classes to give control and history
class ProjectEncounter(db.Model, HoustonModel):

    project_guid = db.Column(db.GUID, db.ForeignKey('project.guid'), primary_key=True)

    encounter_guid = db.Column(db.GUID, db.ForeignKey('encounter.guid'), primary_key=True)

    project = db.relationship('Project', back_populates='encounter_members')

    encounter = db.relationship('Encounter', back_populates='projects')


class ProjectUserMembershipEnrollment(db.Model, HoustonModel):

    project_guid = db.Column(db.GUID, db.ForeignKey('project.guid'), primary_key=True)

    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), primary_key=True)

    project = db.relationship('Project', back_populates='user_membership_enrollments')

    user = db.relationship('User', back_populates='project_membership_enrollments')


class Project(db.Model, HoustonModel, Timestamp):
    """
    Projects database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    title = db.Column(db.String(length=50), nullable=False)

    user_membership_enrollments = db.relationship(
        'ProjectUserMembershipEnrollment', back_populates='project'
    )

    encounter_members = db.relationship('ProjectEncounter', back_populates='project')

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            "title='{self.title}'"
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @property
    def members(self):
        return [enrollment.user for enrollment in self.user_membership_enrollments]

    @property
    def encounters(self):
        return [member.encounter for member in self.encounter_members]

    @db.validates('title')
    def validate_title(self, key, title):  # pylint: disable=unused-argument,no-self-use
        if len(title) < 3:
            raise ValueError('Title has to be at least 3 characters long.')
        return title

    def has_read_permission(self, user, obj):
        from app.modules.encounters.models import Encounter

        # Allow user to read the project details
        has_permission = obj == self

        if not has_permission:
            if isinstance(obj, Encounter):
                # Optionally add time check so that User can only access encounters after user was added to project
                has_permission = obj in self.encounters
            else:
                for encounter in self.encounters:
                    # If time check was implemented, that would need to be passed here too and percolate down through
                    # encounters and sightings etc
                    has_permission = encounter.has_read_permission(obj)
                    if has_permission:
                        break

        return has_permission

    def add_user(self, user):
        enrollment = ProjectUserMembershipEnrollment(
            project=self,
            user=user,
        )

        with db.session.begin():
            self.user_membership_enrollments.append(enrollment)
