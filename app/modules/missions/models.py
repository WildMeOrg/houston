# -*- coding: utf-8 -*-
"""
Missions database models
--------------------
"""
import uuid

from app.extensions import db, HoustonModel, Timestamp


class MissionUserMembershipEnrollment(db.Model, HoustonModel):

    mission_guid = db.Column(db.GUID, db.ForeignKey('mission.guid'), primary_key=True)

    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), primary_key=True)

    mission = db.relationship('Mission', back_populates='user_membership_enrollments')

    # user = db.relationship('User', back_populates='mission_membership_enrollments')
    user = db.relationship('User', backref=db.backref('mission_membership_enrollments'))


class Mission(db.Model, HoustonModel, Timestamp):
    """
    Missions database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    title = db.Column(db.String(length=50), nullable=False)

    user_membership_enrollments = db.relationship(
        'MissionUserMembershipEnrollment', back_populates='mission'
    )

    owner_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=False
    )
    # owner = db.relationship('User', back_populates='owned_missions')
    owner = db.relationship(
        'User', 
        backref=db.backref('owned_missions'), 
        primaryjoin='User.guid == Mission.owner_guid',
        order_by='Mission.guid',
    )

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

    @db.validates('title')
    def validate_title(self, key, title):  # pylint: disable=unused-argument,no-self-use
        if len(title) < 3:
            raise ValueError('Title has to be at least 3 characters long.')
        return title

    def add_user(self, user):
        with db.session.begin():
            self.add_user_in_context(user)

    def add_user_in_context(self, user):
        enrollment = MissionUserMembershipEnrollment(
            mission=self,
            user=user,
        )

        db.session.add(enrollment)
        self.user_membership_enrollments.append(enrollment)

    def remove_user_in_context(self, user):
        for member in self.user_membership_enrollments:
            if member.user == user:
                db.session.delete(member)
                break

    def delete(self):
        with db.session.begin():
            while self.user_membership_enrollments:
                db.session.delete(self.user_membership_enrollments.pop())
            db.session.delete(self)
