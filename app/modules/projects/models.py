# -*- coding: utf-8 -*-
"""
Projects database models
--------------------
"""
import uuid

from app.extensions import HoustonModel, Timestamp, db


# All many:many associations handled as Houston model classes to give control and history
class ProjectEncounter(db.Model, HoustonModel):

    project_guid = db.Column(db.GUID, db.ForeignKey('project.guid'), primary_key=True)

    encounter_guid = db.Column(db.GUID, db.ForeignKey('encounter.guid'), primary_key=True)

    project = db.relationship('Project', back_populates='encounter_members')

    encounter = db.relationship('Encounter', backref=db.backref('projects'))


class ProjectUserMembershipEnrollment(db.Model, HoustonModel):

    project_guid = db.Column(db.GUID, db.ForeignKey('project.guid'), primary_key=True)

    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), primary_key=True)

    project = db.relationship('Project', back_populates='user_membership_enrollments')

    # user = db.relationship('User', back_populates='project_membership_enrollments')
    user = db.relationship('User', backref=db.backref('project_membership_enrollments'))


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

    encounter_members = db.relationship(
        'ProjectEncounter',
        back_populates='project',
        order_by='ProjectEncounter.encounter_guid',
    )

    owner_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=False
    )
    # owner = db.relationship('User', back_populates='owned_projects')
    owner = db.relationship(
        'User',
        backref=db.backref(
            'owned_projects',
            primaryjoin='User.guid == Project.owner_guid',
            order_by='Project.guid',
        ),
    )

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.projects.schemas import BaseProjectSchema

        return BaseProjectSchema

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            "title='{self.title}', "
            'members={members} '
            ')>'.format(
                class_name=self.__class__.__name__, self=self, members=self.get_members()
            )
        )

    def get_members(self):
        return [enrollment.user for enrollment in self.user_membership_enrollments]

    def get_encounters(self):
        return [member.encounter for member in self.encounter_members]

    @db.validates('title')
    def validate_title(self, key, title):  # pylint: disable=unused-argument,no-self-use
        if len(title) < 3:
            raise ValueError('Title has to be at least 3 characters long.')
        return title

    def add_user(self, user):
        with db.session.begin():
            self.add_user_in_context(user)

    def add_encounter(self, encounter):
        with db.session.begin():
            self.add_encounter_in_context(encounter)

    def add_user_in_context(self, user):
        enrollment = ProjectUserMembershipEnrollment(
            project=self,
            user=user,
        )

        db.session.add(enrollment)
        self.user_membership_enrollments.append(enrollment)

    def add_encounter_in_context(self, encounter):
        enrollment = ProjectEncounter(
            project=self,
            encounter=encounter,
        )

        db.session.add(enrollment)
        self.encounter_members.append(enrollment)

    def remove_user_in_context(self, user):
        for member in self.user_membership_enrollments:
            if member.user == user:
                db.session.delete(member)
                break

    def remove_encounter_in_context(self, encounter):
        for member in self.encounter_members:
            if member.encounter == encounter:
                db.session.delete(member)
                break

    def delete(self):
        with db.session.begin():
            while self.user_membership_enrollments:
                db.session.delete(self.user_membership_enrollments.pop())
            while self.encounter_members:
                db.session.delete(self.encounter_members.pop())
            db.session.delete(self)
