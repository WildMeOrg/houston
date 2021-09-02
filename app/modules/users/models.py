# -*- coding: utf-8 -*-
"""
User database models
--------------------
"""
import enum
import logging
import uuid

from flask import current_app
from sqlalchemy_utils import types as column_types

from flask_login import current_user  # NOQA
from app.extensions import db, FeatherModel
from app.extensions.auth import security
from app.extensions.edm import EDMObjectMixin
from app.extensions.api.parameters import _get_is_static_role_property
import app.extensions.logging as AuditLog


log = logging.getLogger(__name__)


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
        user = User.query.filter(User.guid == guid).first()
        is_new = user is None

        if is_new:
            email = '%s@localhost' % (guid,)
            password = User.initial_random_password()
            user = User(
                guid=guid,
                email=email,
                password=password,
                version=None,
                is_active=True,
                in_alpha=True,
            )
            with db.session.begin():
                db.session.add(user)
            db.session.refresh(user)

        return user, is_new

    def _process_edm_user_profile_url(self, url):
        # TODO is this actually needed
        log.warning('User._process_edm_profile_url() not implemented yet')

    def _process_edm_user_organization(self, org):
        # TODO is this actually needed
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
    version = db.Column(db.BigInteger, default=None, nullable=True)

    email = db.Column(
        db.String(length=120), index=True, unique=True, default='', nullable=False
    )

    password = db.Column(
        column_types.PasswordType(max_length=128, schemes=('bcrypt',)), nullable=False
    )  # can me migrated from EDM field "password"

    full_name = db.Column(
        db.String(length=120), default='', nullable=False
    )  # can be migrated from EDM field "fullName"
    website = db.Column(
        db.String(length=120), nullable=True
    )  # can be migrated from EDM field "userURL"
    location = db.Column(db.String(length=120), default='', nullable=True)
    affiliation = db.Column(
        db.String(length=120), default='', nullable=True
    )  # can be migrated from BE field "affiliation"
    forum_id = db.Column(db.String(length=120), default='', nullable=True)
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

    profile_fileupload_guid = db.Column(
        db.GUID, db.ForeignKey('file_upload.guid'), nullable=True
    )
    # 'FileUpload' failed to locate a name (class not yet loaded)
    # so explicitly import FileUpload here
    from app.modules.fileuploads.models import FileUpload

    profile_fileupload = db.relationship(FileUpload)

    organization_membership_enrollments = db.relationship(
        'OrganizationUserMembershipEnrollment', back_populates='user'
    )

    organization_moderator_enrollments = db.relationship(
        'OrganizationUserModeratorEnrollment', back_populates='user'
    )

    project_membership_enrollments = db.relationship(
        'ProjectUserMembershipEnrollment', back_populates='user'
    )

    user_collaboration_associations = db.relationship(
        'CollaborationUserAssociations', back_populates='user'
    )

    asset_groups = db.relationship(
        'AssetGroup',
        back_populates='owner',
        primaryjoin='User.guid == AssetGroup.owner_guid',
        order_by='AssetGroup.guid',
    )

    submitted_asset_groups = db.relationship(
        'AssetGroup',
        back_populates='submitter',
        primaryjoin='User.guid == AssetGroup.submitter_guid',
        order_by='AssetGroup.guid',
    )

    owned_encounters = db.relationship(
        'Encounter',
        back_populates='owner',
        primaryjoin='User.guid == Encounter.owner_guid',
        order_by='Encounter.guid',
    )

    submitted_encounters = db.relationship(
        'Encounter',
        back_populates='submitter',
        primaryjoin='User.guid == Encounter.submitter_guid',
        order_by='Encounter.guid',
    )

    owned_organizations = db.relationship(
        'Organization',
        back_populates='owner',
        primaryjoin='User.guid == Organization.owner_guid',
        order_by='Organization.guid',
    )

    owned_projects = db.relationship(
        'Project',
        back_populates='owner',
        primaryjoin='User.guid == Project.owner_guid',
        order_by='Project.guid',
    )

    # User may have many notifications
    notifications = db.relationship(
        'Notification',
        back_populates='recipient',
        primaryjoin='User.guid == Notification.recipient_guid',
        order_by='Notification.guid',
    )

    # All User specific Notification Preferences will be held in one instance
    notification_preferences = db.relationship(
        'UserNotificationPreferences',
        back_populates='user',
        primaryjoin='User.guid == UserNotificationPreferences.user_guid',
        order_by='UserNotificationPreferences.guid',
    )

    PUBLIC_USER_EMAIL = 'public@localhost'

    class StaticRoles(enum.Enum):
        # pylint: disable=missing-docstring,unsubscriptable-object
        DATA_MANAGER = (0x100000, 'DataManager', 'DataManager', 'is_data_manager')
        USER_MANAGER = (0x80000, 'UserManager', 'UserManager', 'is_user_manager')
        CONTRIBUTOR = (0x40000, 'Contributor', 'Contributor', 'is_contributor')
        RESEARCHER = (0x20000, 'Researcher', 'Researcher', 'is_researcher')
        EXPORTER = (0x10000, 'Exporter', 'Exporter', 'is_exporter')

        INTERNAL = (0x08000, 'Internal', 'Internal', 'is_internal')
        ADMIN = (0x04000, 'Site Administrator', 'Admin', 'is_admin')
        STAFF = (0x02000, 'Staff Member', 'Staff', 'is_staff')
        ACTIVE = (0x01000, 'Active Account', 'Active', 'is_active')

        SETUP = (0x00800, 'Account in Setup', 'Setup', 'in_setup')
        RESET = (0x00400, 'Account in Password Reset', 'Reset', 'in_reset')
        ALPHA = (0x00200, 'Enrolled in Alpha', 'Alpha', 'in_alpha')
        BETA = (0x00100, 'Enrolled in Beta', 'Beta', 'in_beta')

        @property
        def mask(self):
            return self.value[0]

        @property
        def title(self):
            return self.value[1]

        @property
        def shorthand(self):
            return self.value[2]

    static_roles = db.Column(db.Integer, default=0, nullable=False)

    is_contributor = _get_is_static_role_property(
        'is_contributor', StaticRoles.CONTRIBUTOR
    )
    is_user_manager = _get_is_static_role_property(
        'is_user_manager', StaticRoles.USER_MANAGER
    )
    is_data_manager = _get_is_static_role_property(
        'is_data_manager', StaticRoles.DATA_MANAGER
    )
    is_researcher = _get_is_static_role_property('is_researcher', StaticRoles.RESEARCHER)
    is_exporter = _get_is_static_role_property('is_exporter', StaticRoles.EXPORTER)
    is_internal = _get_is_static_role_property('is_internal', StaticRoles.INTERNAL)
    is_admin = _get_is_static_role_property('is_admin', StaticRoles.ADMIN)
    is_staff = _get_is_static_role_property('is_staff', StaticRoles.STAFF)
    is_active = _get_is_static_role_property('is_active', StaticRoles.ACTIVE)

    in_beta = _get_is_static_role_property('in_beta', StaticRoles.BETA)
    in_alpha = _get_is_static_role_property('in_alpha', StaticRoles.ALPHA)

    in_reset = _get_is_static_role_property('in_reset', StaticRoles.RESET)
    in_setup = _get_is_static_role_property('in_setup', StaticRoles.SETUP)

    @property
    def is_privileged(self):
        return self.is_staff or self.is_internal

    def get_state(self):
        state = []
        state += [self.StaticRoles.ACTIVE.shorthand] if self.is_active else []
        state += [self.StaticRoles.SETUP.shorthand] if self.in_setup else []
        state += [self.StaticRoles.RESET.shorthand] if self.in_reset else []
        state += [self.StaticRoles.ALPHA.shorthand] if self.in_alpha else []
        state += [self.StaticRoles.BETA.shorthand] if self.in_beta else []
        return state

    def get_roles(self):
        roles = []
        roles += [self.StaticRoles.DATA_MANAGER.shorthand] if self.is_data_manager else []
        roles += [self.StaticRoles.USER_MANAGER.shorthand] if self.is_user_manager else []
        roles += [self.StaticRoles.INTERNAL.shorthand] if self.is_internal else []
        roles += [self.StaticRoles.ADMIN.shorthand] if self.is_admin else []
        roles += [self.StaticRoles.STAFF.shorthand] if self.is_staff else []
        roles += [self.StaticRoles.CONTRIBUTOR.shorthand] if self.is_contributor else []
        roles += [self.StaticRoles.RESEARCHER.shorthand] if self.is_researcher else []
        roles += [self.StaticRoles.EXPORTER.shorthand] if self.is_exporter else []
        return roles

    def __repr__(self):
        state = ', '.join(self.get_state())
        roles = ', '.join(self.get_roles())

        return (
            '<{class_name}('
            'guid={self.guid}, '
            'email="{self.email}", '
            'name="{self.full_name}", '
            'state={state}, '
            'roles={roles}'
            ')>'.format(
                class_name=self.__class__.__name__, self=self, state=state, roles=roles
            )
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
        is_researcher=False,
        is_contributor=True,
        is_user_manager=False,
        is_exporter=False,
        is_active=True,
        in_beta=False,
        in_alpha=False,
        update=False,
        **kwargs,
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
                is_researcher=is_researcher,
                is_contributor=is_contributor,
                is_user_manager=is_user_manager,
                is_exporter=is_exporter,
                in_beta=in_beta,
                in_alpha=in_alpha,
                **kwargs,
            )

            with db.session.begin():
                db.session.add(user)

            log.info('New user created: %r' % (user,))
        elif update:
            user.password = password
            user.is_internal = is_internal
            user.is_admin = is_admin
            user.is_staff = is_staff
            user.is_researcher = is_researcher
            user.is_contributor = is_contributor
            user.is_user_manager = is_user_manager
            user.is_exporter = is_exporter
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

    def get_org_memberships(self):
        return [
            enrollment.organization
            for enrollment in self.organization_membership_enrollments
        ]

    def get_org_moderatorships(self):
        return [
            enrollment.organization
            for enrollment in self.organization_moderator_enrollments
        ]

    def get_projects(self):
        return [enrollment.project for enrollment in self.project_membership_enrollments]

    def get_collaborations_as_json(self):
        from app.modules.collaborations.schemas import DetailedCollaborationSchema

        json_resp = []
        for collab_assoc in self.user_collaboration_associations:
            json_resp.append(
                DetailedCollaborationSchema().dump(collab_assoc.collaboration).data
            )
        return json_resp

    def get_notification_preferences(self):
        from app.modules.notifications.models import UserNotificationPreferences

        # User preferences are the system ones plus the ones stored in this class
        # Return the combination to the REST API
        preferences = UserNotificationPreferences.get_user_preferences(self)
        return preferences

    def unprocessed_asset_groups(self):
        return [
            asset_group.guid
            for asset_group in self.asset_groups
            if not asset_group.is_processed()
        ]

    def unprocessed_sightings(self):
        from app.modules.sightings.models import SightingStage

        return [
            sighting.guid
            for sighting in self.get_sightings()
            if not sighting.stage == SightingStage.processed
        ]

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

    def owns_object(self, obj):
        from app.modules.assets.models import Asset
        from app.modules.asset_groups.models import AssetGroup
        from app.modules.encounters.models import Encounter
        from app.modules.sightings.models import Sighting
        from app.modules.projects.models import Project
        from app.modules.individuals.models import Individual
        from app.modules.notifications.models import Notification

        ret_val = False

        if isinstance(obj, User):
            ret_val = obj == self
        # AssetGroup, Encounters and Projects all have an owner field, check that
        elif isinstance(obj, (AssetGroup, Encounter, Project, Notification)):
            ret_val = obj.owner == self
        elif isinstance(obj, Asset):
            # assets are not owned directly by the user but the asset_group they're in is.
            # TODO: need to understand once assets become part of an encounter, do they still have a asset_group
            if obj.asset_group is not None:
                ret_val = obj.asset_group.owner is self
        elif isinstance(obj, Sighting):
            # decided (2021-03-12) that "owner" of a Sighting is not applicable therefore always False
            #   permissions must be handled in ways not dependent on ownership
            ret_val = False
        elif isinstance(obj, Individual):
            for encounter in obj.get_encounters():
                if encounter.get_owner() is self:
                    ret_val = True
                    break

        return ret_val

    def get_my_annotations(self):
        annotations = []
        for encounter in self.owned_encounters:
            annotations.extend(encounter.annotations)
        return annotations

    def get_all_encounters(self):
        annotations = self.get_my_annotations()
        # TODO add collaboration annotations
        return annotations

    def delete(self):
        with db.session.begin():
            # TODO: Ensure proper cleanup
            for asset_group in self.asset_groups:
                asset_group.delete()
            AuditLog.delete_object(log, self)
            db.session.delete(self)

    @classmethod
    def initial_random_password(cls):
        return security.generate_random(128)

    @classmethod
    def get_public_user(cls):
        return User.ensure_user(
            email=User.PUBLIC_USER_EMAIL,
            password=User.initial_random_password(),
            full_name='Public User',
            is_internal=True,
        )

    def get_sightings(self):
        sightings = []
        for encounter in self.owned_encounters:
            sighting = encounter.get_sighting()
            if sighting:
                sightings.append(encounter.get_sighting())

        sighting_set = set(sightings)
        return list(sighting_set)


USER_ROLES = [
    role.value[-1]
    for role in User.StaticRoles.__members__.values()
    if role.value[-1] not in ('in_setup', 'in_reset')
]
