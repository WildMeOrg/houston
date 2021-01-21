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
            "title='{self.title}', "
            'members={self.members} '
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

    def add_user(self, user):
        enrollment = ProjectUserMembershipEnrollment(
            project=self,
            user=user,
        )

        with db.session.begin():
            db.session.add(enrollment)
            self.user_membership_enrollments.append(enrollment)

    def add_encounter(self, encounter):
        enrollment = ProjectEncounter(
            project=self,
            encounter=encounter,
        )

        with db.session.begin():
            db.session.add(enrollment)
            self.encounter_members.append(enrollment)

    def delete(self):
        with db.session.begin():
            while self.user_membership_enrollments:
                db.session.delete(self.user_membership_enrollments.pop())
            while self.encounter_members:
                db.session.delete(self.encounter_members.pop())
            db.session.delete(self)

    def set_field(self, field, value):
        ret_val = True
        from app.modules.users.models import User
        from app.modules.encounters.models import Encounter

        if field == 'User':
            user = User.query.get(value)
            if user:
                self.add_user(user)
            else:
                ret_val = False

        if field == 'Encounter':
            encounter = Encounter.query.get(value)
            if encounter:
                self.add_encounter(encounter)
            else:
                ret_val = False
        return ret_val

    def forget_field(self, field):
        # This doesn't work. For the forget we need a value to forget in the many:many relationship
        return False
