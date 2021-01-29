# -*- coding: utf-8 -*-
"""
Organizations database models
--------------------
"""

from flask import current_app
from app.extensions import db, HoustonModel
from app.extensions.edm import EDMObjectMixin

import logging
import uuid
import datetime
import pytz

log = logging.getLogger(__name__)


class OrganizationEDMMixin(EDMObjectMixin):
    # All comms with EDM to exchange timestamps will use this format so it should be in one place
    # todo, does this make sense? Does anything in EDM other than Organizations have this time format
    EDM_DATETIME_FMTSTR = '%Y-%m-%dT%H:%M:%S.%fZ'

    # fmt: off
    # Name of the module, used for knowing what to sync i.e organization.list, organization.data
    EDM_NAME = 'organization'

    # The EDM attribute for the version, if reported
    EDM_VERSION_ATTRIBUTE = 'version'

    #
    EDM_LOG_ATTRIBUTES = [
        'name',
    ]

    # todo Very much a first drop of mapping
    EDM_ATTRIBUTE_MAPPING = {
        # Ignored
        'id'                    : None,
        'created'               : None,
        'modified'              : None,

        # # Attributes
        'name'                  : 'title',
        'url'                   : 'website',
        'version'               : 'version',

        # # Functions
        'members'               : '_process_members',
        'logo'                  : '_process_logo',
        'createdDate'           : '_process_created_date',
        'modifiedDate'          : '_process_modified_date',
    }
    # fmt: on

    @classmethod
    def ensure_edm_obj(cls, guid):
        organization = Organization.query.filter(Organization.guid == guid).first()
        is_new = False

        if organization is None:
            organization = Organization(
                guid=guid,
                title='none',
            )
            db.session.add(organization)
            is_new = True

        return organization, is_new

    # Helper function for converting time in the EDM database to local time
    @classmethod
    def edm_to_local_time(cls, edm_date_time):
        naive_time = datetime.datetime.strptime(edm_date_time, cls.EDM_DATETIME_FMTSTR)
        # tell it that it's actually UTC, without this, the hour decrements
        utc_tz = pytz.timezone('UTC')
        utc_time = utc_tz.localize(naive_time)
        return utc_time.astimezone(current_app.config.get('TIMEZONE'))

    def _process_members(self, members):
        from app.modules.users.models import User

        for member in members:
            log.info('Adding Member ID %s' % (member.id,))
            user, is_new = User.ensure_edm_obj(member.id)
            if user not in self.members:
                enrollment = OrganizationUserMembershipEnrollment(
                    organization=self,
                    user=user,
                )

                with db.session.begin():
                    self.user_membership_enrollments.append(enrollment)

    def _process_logo(self, logo):
        self.logo_guid = logo.uuid
        self.logo_url = logo.url

    def _process_created_date(self, created_date):
        self.created = self.edm_to_local_time(created_date)

    def _process_modified_date(self, modified_date):
        self.updated = self.edm_to_local_time(modified_date)


class OrganizationUserMembershipEnrollment(db.Model, HoustonModel):

    organization_guid = db.Column(
        db.GUID, db.ForeignKey('organization.guid'), primary_key=True
    )

    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), primary_key=True)

    organization = db.relationship(
        'Organization', back_populates='user_membership_enrollments'
    )

    user = db.relationship('User', back_populates='organization_membership_enrollments')


class OrganizationUserModeratorEnrollment(db.Model, HoustonModel):

    organization_guid = db.Column(
        db.GUID, db.ForeignKey('organization.guid'), primary_key=True
    )

    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), primary_key=True)

    organization = db.relationship('Organization', back_populates='moderator_enrollments')

    user = db.relationship('User', back_populates='organization_moderator_enrollments')


class Organization(db.Model, HoustonModel, OrganizationEDMMixin):
    """
    Organizations database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    version = db.Column(db.Integer, default=None, nullable=True)
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

    owner_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=False
    )
    owner = db.relationship('User', backref=db.backref('owned_organizations'))

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
