# -*- coding: utf-8 -*-
"""
Organizations database models
--------------------
"""
import logging
import uuid

from app.extensions import HoustonModel, db

log = logging.getLogger(__name__)


class OrganizationUserMembershipEnrollment(db.Model, HoustonModel):

    organization_guid = db.Column(
        db.GUID, db.ForeignKey('organization.guid'), primary_key=True
    )

    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), primary_key=True)

    organization = db.relationship(
        'Organization', back_populates='user_membership_enrollments'
    )

    # user = db.relationship('User', back_populates='organization_membership_enrollments')
    user = db.relationship(
        'User', backref=db.backref('organization_membership_enrollments')
    )


class OrganizationUserModeratorEnrollment(db.Model, HoustonModel):

    organization_guid = db.Column(
        db.GUID, db.ForeignKey('organization.guid'), primary_key=True
    )

    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), primary_key=True)

    organization = db.relationship('Organization', back_populates='moderator_enrollments')

    # user = db.relationship('User', back_populates='organization_moderator_enrollments')
    user = db.relationship(
        'User', backref=db.backref('organization_moderator_enrollments')
    )


class Organization(db.Model, HoustonModel):
    """
    Organizations database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    version = db.Column(db.BigInteger, default=None, nullable=True)
    title = db.Column(db.String(length=50), nullable=False)

    logo_guid = db.Column(db.GUID, default=uuid.uuid4, nullable=True)
    logo_url = db.Column(db.String(length=200), nullable=True)

    website = db.Column(db.String(length=120), nullable=True)

    user_membership_enrollments = db.relationship(
        'OrganizationUserMembershipEnrollment', back_populates='organization'
    )

    moderator_enrollments = db.relationship(
        'OrganizationUserModeratorEnrollment', back_populates='organization'
    )

    owner_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True)
    # owner = db.relationship('User', back_populates='owned_organizations')
    owner = db.relationship(
        'User',
        backref=db.backref(
            'owned_organizations',
            primaryjoin='User.guid == Organization.owner_guid',
            order_by='Organization.guid',
        ),
    )

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'title="{self.title}", '
            'website={self.website}, '
            'logo={self.logo_url}, '
            'members={members}, '
            ')>'.format(
                class_name=self.__class__.__name__, self=self, members=self.get_members()
            )
        )

    def get_members(self):
        return [enrollment.user for enrollment in self.user_membership_enrollments]

    def get_moderators(self):
        return [enrollment.user for enrollment in self.moderator_enrollments]

    @db.validates('title')
    def validate_title(self, key, title):  # pylint: disable=unused-argument,no-self-use
        if len(title) < 3:
            raise ValueError('Title has to be at least 3 characters long.')
        return title

    def add_user(self, user):
        with db.session.begin():
            self.add_user_in_context(user)

    def add_moderator(self, user):
        with db.session.begin():
            self.add_moderator_in_context(user)

    def add_user_in_context(self, user):
        enrollment = OrganizationUserMembershipEnrollment(
            organization=self,
            user=user,
        )

        db.session.add(enrollment)
        self.user_membership_enrollments.append(enrollment)

    def add_moderator_in_context(self, user):
        enrollment = OrganizationUserModeratorEnrollment(
            organization=self,
            user=user,
        )

        db.session.add(enrollment)
        self.moderator_enrollments.append(enrollment)

    def delete(self):
        with db.session.begin():
            while self.user_membership_enrollments:
                db.session.delete(self.user_membership_enrollments.pop())
            while self.moderator_enrollments:
                db.session.delete(self.moderator_enrollments.pop())
            db.session.delete(self)
