# -*- coding: utf-8 -*-
"""
User database models
--------------------
"""
import enum
import logging

from flask import url_for, current_app
from sqlalchemy_utils import types as column_types

from flask_login import current_user  # NOQA
from app.extensions import db, FeatherModel
from app.extensions.auth import security
from app.extensions.edm import EDMObjectMixin
from app.extensions.api.parameters import _get_is_static_role_property

from app.modules.assets.models import Asset

import pytz
import uuid

import tqdm

log = logging.getLogger(__name__)


PST = pytz.timezone('US/Pacific')


class UserEDMMixin(EDMObjectMixin):

    # fmt: off
    # Name of the module, used for knowing what to sync i.e user.list, user.data
    EDM_NAME = 'user'

    # The EDM attribute for the version, if reported
    EDM_VERSION_ATTRIBUTE = 'version'

    #
    EDM_LOG_ATTRIBUTES = [
        'emailAddress',
    ]

    EDM_ATTRIBUTE_MAPPING = {
        # Ignored
        'id'                    : None,
        'lastLogin'             : None,
        'username'              : None,

        # Attributes
        'acceptedUserAgreement' : 'accepted_user_agreement',
        'affiliation'           : 'affiliation',
        'emailAddress'          : 'email',
        'fullName'              : 'full_name',
        'receiveEmails'         : 'receive_notification_emails',
        'sharing'               : 'shares_data',
        'userURL'               : 'website',
        'version'               : 'version',

        # Functions
        'organizations'         : '_process_edm_user_organization',
        'profileImageUrl'       : '_process_edm_user_profile_url',
    }
    # fmt: on

    @classmethod
    def ensure_edm_obj(cls, guid):
        with db.session.begin():
            user = User.query.filter(User.guid == guid).first()
            is_new = False

            if user is None:
                email = '%s@localhost' % (guid,)
                password = security.generate_random(128)
                user = User(
                    guid=guid,
                    email=email,
                    password=password,
                    version=None,
                    is_active=True,
                    in_alpha=True,
                )
                db.session.add(user)
                is_new = True

        return user, is_new

    def _process_edm_user_profile_url(self, url):
        log.warning('User._process_edm_profile_url() not implemented yet')

    def _process_edm_user_organization(self, org):
        log.warning('User._process_edm_user_organization() not implemented yet')


class User(db.Model, FeatherModel, UserEDMMixin):
    """
    User database model.

    TODO:
    * Upgrade to HoustonModel after full transition for Users out of EDM is
      complete
    """

    def __init__(self, *args, **kwargs):
        if 'password' not in kwargs:
            raise ValueError('User must have a password')
        super().__init__(*args, **kwargs)

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    version = db.Column(db.Integer, default=None, nullable=True)

    email = db.Column(db.String(length=120), index=True, unique=True, nullable=False)

    password = db.Column(
        column_types.PasswordType(max_length=128, schemes=('bcrypt',)), nullable=False
    )  # can me migrated from EDM field "password"

    full_name = db.Column(
        db.String(length=120), default='', nullable=False
    )  # can be migrated from EDM field "fullName"
    website = db.Column(
        db.String(length=120), nullable=True
    )  # can be migrated from EDM field "userURL"
    location = db.Column(db.String(length=120), nullable=True)
    affiliation = db.Column(
        db.String(length=120), nullable=True
    )  # can be migrated from BE field "affiliation"
    forum_id = db.Column(db.String(length=120), nullable=True)
    locale = db.Column(db.String(length=20), default='EN', nullable=True)

    accepted_user_agreement = db.Column(
        db.Boolean, default=False, nullable=False
    )  # can be migrated from EDM field "acceptedUserAgreement"
    use_usa_date_format = db.Column(db.Boolean, default=True, nullable=False)
    show_email_in_profile = db.Column(db.Boolean, default=False, nullable=False)
    receive_notification_emails = db.Column(
        db.Boolean, default=True, nullable=False
    )  # can be migrated from BE field "receiveEmails"
    receive_newsletter_emails = db.Column(db.Boolean, default=False, nullable=False)
    shares_data = db.Column(
        db.Boolean, default=True, nullable=False
    )  # can be migrated from BE field "sharing"

    default_identification_catalogue = db.Column(
        db.GUID, nullable=True
    )  # this may just be a string, however EDM wants to do ID catalogues

    profile_asset_guid = db.Column(
        db.GUID, nullable=True
    )  # should be reconciled with Jon's MediaAsset class
    footer_logo_asset_guid = db.Column(
        db.GUID, nullable=True
    )  # should be reconciled with Jon's MediaAsset class

    # This addition causes all of the pytests to fail.
    #organization_guid = db.Column(
    #    db.GUID, db.ForeignKey('organization.guid'), index=True, nullable=True
    #)
    #organization = db.relationship('Organization', backref=db.backref('members'))

    class StaticRoles(enum.Enum):
        # pylint: disable=missing-docstring,unsubscriptable-object
        INTERNAL = (0x8000, 'Internal')
        ADMIN = (0x4000, 'Site Administrator')
        STAFF = (0x2000, 'Staff Member')
        ACTIVE = (0x1000, 'Active Account')

        SETUP = (0x0800, 'Account in Setup')
        RESET = (0x0400, 'Account in Password Reset')
        ALPHA = (0x0200, 'Enrolled in Alpha')
        BETA = (0x0100, 'Enrolled in Beta')

        @property
        def mask(self):
            return self.value[0]

        @property
        def title(self):
            return self.value[1]

    static_roles = db.Column(db.Integer, default=0, nullable=False)

    is_internal = _get_is_static_role_property('is_internal', StaticRoles.INTERNAL)
    is_admin = _get_is_static_role_property('is_admin', StaticRoles.ADMIN)
    is_staff = _get_is_static_role_property('is_staff', StaticRoles.STAFF)
    is_active = _get_is_static_role_property('is_active', StaticRoles.ACTIVE)

    in_beta = _get_is_static_role_property('in_beta', StaticRoles.BETA)
    in_alpha = _get_is_static_role_property('in_alpha', StaticRoles.ALPHA)

    in_reset = _get_is_static_role_property('in_reset', StaticRoles.RESET)
    in_setup = _get_is_static_role_property('in_setup', StaticRoles.SETUP)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'email="{self.email}", '
            'name="{self.full_name}", '
            'is_internal={self.is_internal}, '
            'is_admin={self.is_admin}, '
            'is_staff={self.is_staff}, '
            'is_active={self.is_active}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @classmethod
    def get_admins(cls):
        # used for first run admin creation
        users = cls.query.all()  # NOQA

        admin_users = []
        for user in users:
            # TODO: Remove the check below at a later point after default admin create is removed
            if user.email.endswith('@localhost'):
                continue
            if user.is_admin:
                admin_users.append(user)

        return admin_users

    @classmethod
    def admin_user_initialized(cls):
        # used for first run admin creation
        return len(cls.get_admins()) > 0

    @classmethod
    def ensure_user(
        cls,
        email,
        password,
        is_internal=False,
        is_admin=False,
        is_staff=False,
        is_active=True,
        in_beta=False,
        in_alpha=False,
        update=False,
        **kwargs
    ):
        """
        Create a new user.
        """
        from app.extensions import db

        user = User.find(email=email)

        if user is None:
            user = User(
                password=password,
                email=email,
                is_internal=is_internal,
                is_admin=is_admin,
                is_staff=is_staff,
                is_active=is_active,
                in_beta=in_beta,
                in_alpha=in_alpha,
                **kwargs
            )

            with db.session.begin():
                db.session.add(user)

            log.info('New user created: %r' % (user,))
        elif update:
            user.password = password
            user.is_internal = is_internal
            user.is_admin = is_admin
            user.is_staff = is_staff
            user.is_active = is_active
            user.in_beta = in_beta
            user.in_alpha = in_alpha

            with db.session.begin():
                db.session.merge(user)

            log.info('Updated user: %r' % (user,))

        db.session.refresh(user)

        return user

    @classmethod
    def find(cls, email=None, password=None, edm_login_fallback=True):
        # Look-up via email

        if email is None:
            return None

        email_candidates = [
            email,
            '%s@localhost' % (email,),
        ]
        for email_candidate in email_candidates:

            user = cls.query.filter(User.email == email_candidate).first()

            if password is None:
                # If no password was provided to check, return any user account we find
                if user is not None:
                    return user
            else:
                # Check local Houston password first
                if user is not None:
                    # We found the user, check their provided password
                    if user.password == password:
                        return user

                # As a fallback, check all EDMs if the user can login
                if edm_login_fallback:
                    # We want to check the EDM even if we don't have a local user record
                    if current_app.edm.check_user_login(email_candidate, password):
                        log.info('User authenticated via EDM: %r' % (email_candidate,))

                        if user is not None:
                            # We authenticated a local user against an EDM (but the local password failed)
                            if user.password != password:
                                # The user passed the login with an EDM, update local password
                                log.warning(
                                    "Updating user's local password: %r" % (user,)
                                )
                                user = user.set_password(password)
                            return user
                        else:
                            log.critical(
                                'The user authenticated via EDM but has no local user record'
                            )
                            # Try syncing all users from EDM
                            cls.edm_sync_all()
                            # If the user was just synced, go grab it (recursively) and return
                            user = cls.find(email=email, edm_login_fallback=False)
                            return user

        # If we have gotten here, one of these things happened:
        #    1) the user wasn't found
        #    2) the user's password was provided and was incorrect
        #    3) the user authenticated against the EDM but has no local user record

        return None

    @classmethod
    def query_search(cls, search=None):
        from sqlalchemy import or_, and_
        from app.modules.auth.models import Code, CodeTypes

        if search is not None:
            search = search.strip().split(' ')
            search = [term.strip() for term in search]
            search = [term for term in search if len(term) > 0]

            or_terms = []
            for term in search:
                codes = (
                    Code.query.filter_by(code_type=CodeTypes.checkin)
                    .filter(
                        Code.accept_code.contains(term),
                    )
                    .all()
                )
                code_users = set([])
                for code in codes:
                    if not code.is_expired:
                        code_users.add(code.user.guid)

                or_term = or_(
                    cls.guid.in_(code_users),
                    cls.email.contains(term),
                    cls.affiliation.contains(term),
                    cls.forum_id.contains(term),
                    cls.full_name.contains(term),
                )
                or_terms.append(or_term)
            users = cls.query.filter(and_(*or_terms))
        else:
            users = cls.query

        return users

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_email_confirmed(self):
        from app.modules.auth.models import Code, CodeTypes

        # Get any codes that fit this request
        code = (
            Code.query.filter_by(user=self, code_type=CodeTypes.email)
            .order_by(Code.created.desc())
            .first()
        )
        if code is None:
            return False
        return code.is_resolved

    @property
    def picture(self):
        asset = Asset.query.filter_by(id=self.profile_asset_guid).first()
        if asset is None:
            placeholder_guid = (self.guid % 7) + 1
            filename = 'images/placeholder_profile_%d.png' % (placeholder_guid,)
            return url_for('static', filename=filename)
        return url_for('backend.asset', code=asset.code)

    def get_id(self):
        return self.guid

    def has_static_role(self, role):
        return (self.static_roles & role.mask) != 0

    def set_static_role(self, role):
        if self.has_static_role(role):
            return
        self.static_roles |= role.mask

    def unset_static_role(self, role):
        if not self.has_static_role(role):
            return
        self.static_roles ^= role.mask

    def check_owner(self, user):
        return self == user

    def check_supervisor(self, user):
        return self.check_owner(user)

    def get_codes(self, code_type, **kwargs):
        # This import for Code needs to be local
        from app.modules.auth.models import Code

        code = Code.get(self, code_type, **kwargs)
        return code

    def get_invite_code(self):
        # This import for Code needs to be local
        from app.modules.auth.models import CodeTypes

        return self.get_codes(CodeTypes.invite, replace=True)

    def get_email_confirmation_code(self):
        # This import for Code needs to be local
        from app.modules.auth.models import CodeTypes

        return self.get_codes(CodeTypes.email, replace=True)

    def get_account_recovery_code(self):
        # This import for Code needs to be local
        from app.modules.auth.models import CodeTypes

        return self.get_codes(CodeTypes.recover, replace=True, replace_ttl=None)

    def set_password(self, password):
        if password is None:
            # This function "sets" the password, it's the responsibility of the caller to ensure it's valid
            raise ValueError('Empty password not allowed')

        self.password = password
        with db.session.begin():
            db.session.merge(self)
        db.session.refresh(self)

        return self

    def lockout(self):
        from app.modules.auth.models import OAuth2Client, OAuth2Grant, OAuth2Token, Code

        # Disable permissions
        self.is_staff = False
        self.is_admin = False
        self.is_active = False
        self.in_reset = False
        self.in_setup = False

        with db.session.begin():
            db.session.merge(self)
        db.session.refresh(self)

        # Logout of sessions and API keys
        auth_list = []
        auth_list += OAuth2Token.query.filter_by(user_guid=self.guid).all()
        auth_list += OAuth2Grant.query.filter_by(user_guid=self.guid).all()
        auth_list += OAuth2Client.query.filter_by(user_guid=self.guid).all()
        auth_list += Code.query.filter_by(user_guid=self.guid).all()
        for auth_ in auth_list:
            auth_.delete()

        return self
