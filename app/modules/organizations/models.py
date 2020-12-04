# -*- coding: utf-8 -*-
"""
Organizations database models
--------------------
"""

from app.extensions import db, HoustonModel
from app.extensions.edm import EDMObjectMixin
import logging
import uuid
import datetime
import pytz

# todo, this should be in config.py, not across various files in the system, and yes should be called TIMEZONE, not PST
TIMEZONE = pytz.timezone('US/Pacific')
DATETIME_FMTSTR = '%Y-%m-%dT%H:%M:%S.%fZ'

log = logging.getLogger(__name__)

class OrganizationEDMMixin(EDMObjectMixin):

    # fmt: off
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
    def find_or_create(cls, guid):
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

    @classmethod
    def edm_sync_organizations(cls, verbose=True, refresh=False):
        return cls.edm_sync_all('organization', verbose, refresh)

    def _process_members(self, members):
        for member in members:
            log.warning("Member ID %s" % (member.id,))
        log.warning('OrganizationEDMMixin._process_edm_profile_url() not implemented yet')

    def _process_logo(self, logo):
        self.logoGuid = logo.uuid
        self.logoUrl = logo.url
        log.warning('OrganizationEDMMixin._process_logo() not implemented yet')

    def _process_created_date(self, created_date):
        self.createdDate = datetime.datetime.strptime(created_date, DATETIME_FMTSTR).astimezone(TIMEZONE)

    def _process_modified_date(self, modified_date):
        self.modifiedDate = datetime.datetime.strptime(modified_date, DATETIME_FMTSTR).astimezone(TIMEZONE)

class Organization(db.Model, HoustonModel, OrganizationEDMMixin):
    """
    Organizations database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    version = db.Column(db.Integer, default=None, nullable=True)
    title = db.Column(db.String(length=50), nullable=False)
    # todo why can dateTimes in the auth class be non Nullable but in here the upgrade fails?
    createdDate = db.Column(db.DateTime, default=datetime.datetime.now(tz=TIMEZONE), nullable=True)
    modifiedDate = db.Column(db.DateTime, default=datetime.datetime.now(tz=TIMEZONE), nullable=True)
    # todo, would have thought this should be an array but apparently only Postgres SQL supports arrays
    # Hitting the limits of my knowledge on how to represent this sensibly
    # members = db.Column(db.ARRAY(db.Integer))  # User GUIDs
    logoGuid = db.Column(db.GUID, default=uuid.uuid4, nullable=True)
    logoUrl = db.Column(db.String(length=200), nullable=True)
    website = db.Column(db.String(length=120), nullable=True)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'title={self.title}, '
            'website={self.website}, '
            'logoUrl={self.logoUrl}'
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @db.validates('title')
    def validate_title(self, key, title):  # pylint: disable=unused-argument,no-self-use
        if len(title) < 3:
            raise ValueError('Title has to be at least 3 characters long.')
        return title
