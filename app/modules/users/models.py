# -*- coding: utf-8 -*-
"""
User database models
--------------------
"""
import enum
import logging
import uuid

from flask import url_for
from flask_login import current_user  # NOQA
from sqlalchemy_utils import types as column_types

import app.extensions.logging as AuditLog
from app.extensions import HoustonModel, db
from app.extensions.api.parameters import _get_is_static_role_property
from app.extensions.auth import security
from app.extensions.email import Email
from app.modules import is_module_enabled, module_required

log = logging.getLogger(__name__)


class User(db.Model, HoustonModel):
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
    )

    full_name = db.Column(db.String(length=120), default='', nullable=False)
    website = db.Column(db.String(length=120), nullable=True)
    location = db.Column(db.String(length=120), default='', nullable=True)
    affiliation = db.Column(db.String(length=120), default='', nullable=True)
    forum_id = db.Column(db.String(length=120), default='', nullable=True)
    locale = db.Column(db.String(length=20), default='EN', nullable=True)

    accepted_user_agreement = db.Column(db.Boolean, default=False, nullable=False)
    use_usa_date_format = db.Column(db.Boolean, default=True, nullable=False)
    show_email_in_profile = db.Column(db.Boolean, default=False, nullable=False)
    receive_notification_emails = db.Column(db.Boolean, default=True, nullable=False)
    receive_newsletter_emails = db.Column(db.Boolean, default=False, nullable=False)
    shares_data = db.Column(db.Boolean, default=True, nullable=False)

    default_identification_catalogue = db.Column(
        db.GUID, nullable=True
    )  # this may just be a string, however EDM wants to do ID catalogues

    # these are to connect social accounts and the like
    linked_accounts = db.Column(db.JSON, nullable=True)

    # twitter_username is *temporary* way we link to twitter
    twitter_username = db.Column(db.String, default=None, nullable=True, unique=True)

    profile_fileupload_guid = db.Column(
        db.GUID, db.ForeignKey('file_upload.guid'), nullable=True
    )
    # 'FileUpload' failed to locate a name (class not yet loaded)
    # so explicitly import FileUpload here
    from app.modules.fileuploads.models import FileUpload

    profile_fileupload = db.relationship(FileUpload)

    # organization_membership_enrollments = db.relationship(
    #     'OrganizationUserMembershipEnrollment', back_populates='user'
    # )

    # organization_moderator_enrollments = db.relationship(
    #     'OrganizationUserModeratorEnrollment', back_populates='user'
    # )

    # project_membership_enrollments = db.relationship(
    #     'ProjectUserMembershipEnrollment', back_populates='user'
    # )

    # user_collaboration_associations = db.relationship(
    #     'CollaborationUserAssociations', back_populates='user'
    # )

    # asset_groups = db.relationship(
    #     'AssetGroup',
    #     back_populates='owner',
    #     primaryjoin='User.guid == AssetGroup.owner_guid',
    #     order_by='AssetGroup.guid',
    # )

    # submitted_asset_groups = db.relationship(
    #     'AssetGroup',
    #     back_populates='submitter',
    #     primaryjoin='User.guid == AssetGroup.submitter_guid',
    #     order_by='AssetGroup.guid',
    # )

    # owned_encounters = db.relationship(
    #     'Encounter',
    #     back_populates='owner',
    #     primaryjoin='User.guid == Encounter.owner_guid',
    #     order_by='Encounter.guid',
    # )

    # submitted_encounters = db.relationship(
    #     'Encounter',
    #     back_populates='submitter',
    #     primaryjoin='User.guid == Encounter.submitter_guid',
    #     order_by='Encounter.guid',
    # )

    # owned_organizations = db.relationship(
    #     'Organization',
    #     back_populates='owner',
    #     primaryjoin='User.guid == Organization.owner_guid',
    #     order_by='Organization.guid',
    # )

    # owned_projects = db.relationship(
    #     'Project',
    #     back_populates='owner',
    #     primaryjoin='User.guid == Project.owner_guid',
    #     order_by='Project.guid',
    # )

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
        INTERPRETER = (0x200000, 'Interpreter', 'Interpreter', 'is_interpreter')

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
    is_interpreter = _get_is_static_role_property(
        'is_interpreter', StaticRoles.INTERPRETER
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
        roles += [self.StaticRoles.USER_MANAGER.shorthand] if self.is_user_manager else []
        roles += [self.StaticRoles.INTERNAL.shorthand] if self.is_internal else []
        roles += [self.StaticRoles.ADMIN.shorthand] if self.is_admin else []
        roles += [self.StaticRoles.STAFF.shorthand] if self.is_staff else []
        roles += [self.StaticRoles.CONTRIBUTOR.shorthand] if self.is_contributor else []
        roles += [self.StaticRoles.RESEARCHER.shorthand] if self.is_researcher else []
        roles += [self.StaticRoles.EXPORTER.shorthand] if self.is_exporter else []

        if is_module_enabled('missions'):
            roles += (
                [self.StaticRoles.INTERPRETER.shorthand] if self.is_interpreter else []
            )

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
    def get_elasticsearch_schema(cls):
        from app.modules.users.schemas import UserListSchema

        return UserListSchema

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
        is_contributor=False,
        is_user_manager=False,
        is_exporter=False,
        is_active=True,
        in_beta=False,
        in_alpha=False,
        update=False,
        send_verification=True,
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

            with db.session.begin(subtransactions=True):
                db.session.add(user)

            if send_verification:
                user.send_verify_account_email()

            log.info('New user created: {!r}'.format(user))
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

            log.info('Updated user: {!r}'.format(user))

        db.session.refresh(user)

        return user

    @classmethod
    def find(cls, email=None, password=None):
        # Look-up via email
        from sqlalchemy import func

        if email is None:
            return None

        email_candidates = [
            email,
            '{}@localhost'.format(email),
        ]
        for email_candidate in email_candidates:

            user = cls.query.filter(
                func.lower(User.email) == func.lower(email_candidate)
            ).first()

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

        # If we have gotten here, one of these things happened:
        #    1) the user wasn't found
        #    2) the user's password was provided and was incorrect

        return None

    @classmethod
    def query_search_term_hook(cls, term):
        from sqlalchemy import String
        from sqlalchemy_utils.functions import cast_if

        return (
            cast_if(cls.guid, String).contains(term),
            cls.email.contains(term),
            cls.affiliation.contains(term),
            cls.forum_id.contains(term),
            cls.full_name.contains(term),
        )

    @classmethod
    def find_by_linked_account(cls, account_key, value, id_key='id'):
        possible = User.query.filter(User.linked_accounts.isnot(None)).all()
        for user in possible:
            if (
                user.linked_accounts
                and account_key in user.linked_accounts
                and user.linked_accounts[account_key].get(id_key) == value
            ):
                return user
        return None

    def link_account(self, social_key, data):
        if not isinstance(data, dict):
            raise ValueError('must pass data as dict')
        if not self.linked_accounts:
            self.linked_accounts = {social_key: data}
        else:
            self.linked_accounts[social_key] = data
            self.linked_accounts = self.linked_accounts
        with db.session.begin():
            db.session.merge(self)
        db.session.refresh(self)

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

    # creates email code and resolves it so above returns true
    def bypass_email_confirmation(self):
        from app.modules.auth.models import CodeDecisions

        code = self.get_email_confirmation_code()
        code.record(CodeDecisions.accept)

    @property
    def owned_missions(self):
        return self.get_owned_missions()

    @property
    def owned_mission_tasks(self):
        return self.get_owned_mission_tasks()

    @property
    def assigned_missions(self):
        return self.get_assigned_missions()

    @property
    def assigned_mission_tasks(self):
        return self.get_assigned_mission_tasks()

    @module_required('organizations', resolve='warn', default=[])
    def get_org_memberships(self):
        return [
            enrollment.organization
            for enrollment in self.organization_membership_enrollments
        ]

    @module_required('organizations', resolve='warn', default=[])
    def get_org_moderatorships(self):
        return [
            enrollment.organization
            for enrollment in self.organization_moderator_enrollments
        ]

    @module_required('projects', resolve='warn', default=[])
    def get_projects(self):
        return [enrollment.project for enrollment in self.project_membership_enrollments]

    @module_required('missions', resolve='warn', default=[])
    def get_owned_missions(self):
        return self.mission_ownerships

    @module_required('missions', resolve='warn', default=[])
    def get_owned_mission_tasks(self):
        return self.mission_task_ownerships

    @module_required('missions', resolve='warn', default=[])
    def get_assigned_missions(self):
        return [assignment.mission for assignment in self.mission_assignments]

    @module_required('missions', resolve='warn', default=[])
    def get_assigned_mission_tasks(self):
        return [assignment.mission_task for assignment in self.mission_task_assignments]

    @module_required('collaborations', resolve='warn', default=[])
    def get_collaborations_as_json(self):
        from app.modules.collaborations.schemas import DetailedCollaborationSchema

        json_resp = []
        for collab_assoc in self.user_collaboration_associations:
            json_resp.append(
                DetailedCollaborationSchema().dump(collab_assoc.collaboration).data
            )
        return json_resp

    @module_required('collaborations', resolve='warn', default=[])
    def get_collaboration_associations(self):
        return self.user_collaboration_associations

    @module_required('notifications', resolve='warn', default=[])
    def get_notification_preferences(self):
        from app.modules.notifications.models import UserNotificationPreferences

        # User preferences are the system ones plus the ones stored in this class
        # Return the combination
        preferences = UserNotificationPreferences.get_user_preferences(self)
        return preferences

    @module_required('individuals', resolve='warn', default=[])
    def get_individual_merge_requests(self):
        from app.modules.individuals.models import Individual

        reqs = Individual.get_active_merge_requests(self)
        return reqs

    @module_required('asset_groups', resolve='warn', default=[])
    def get_asset_groups(self):
        from app.extensions.git_store import GitStore
        from app.modules.asset_groups.models import AssetGroup

        return GitStore.filter_for(AssetGroup, self.git_stores)

    @module_required('asset_groups', resolve='warn', default=[])
    def get_unprocessed_asset_groups(self):
        from app.modules.asset_groups.models import (
            AssetGroup,
            AssetGroupSighting,
            AssetGroupSightingStage,
        )

        return (
            db.session.query(AssetGroup)
            .join(AssetGroupSighting)
            .filter(AssetGroup.owner_guid == self.guid)
            .filter(AssetGroupSighting.stage != AssetGroupSightingStage.processed)
        ).all()

    # this is used for the users/me schema output
    @module_required('asset_groups', resolve='warn', default=[])
    def unprocessed_asset_groups(self):
        unprocessed_groups = self.get_unprocessed_asset_groups()
        return [
            {
                'uuid': str(asset_group.guid),
                'uploadType': asset_group.get_config_field('uploadType'),
            }
            for asset_group in unprocessed_groups
        ]

    @module_required('asset_groups', resolve='warn', default=[])
    def get_unprocessed_asset_group_sightings(self):
        from app.modules.asset_groups.models import (
            AssetGroup,
            AssetGroupSighting,
            AssetGroupSightingStage,
        )

        query = (
            db.session.query(AssetGroupSighting)
            .join(AssetGroup)
            .filter(AssetGroup.owner_guid == self.guid)
            .filter(AssetGroupSighting.stage != AssetGroupSightingStage.processed)
        )

        return query

    @module_required('sightings', resolve='warn', default=[])
    def unprocessed_sightings(self):
        from app.modules.sightings.models import SightingMatchState

        return [
            sighting.guid
            for sighting in self.get_sightings()
            if not (
                sighting.match_state == SightingMatchState.reviewed
                or sighting.match_state == SightingMatchState.unidentifiable
            )
        ]

    @module_required('sightings', resolve='warn', default=[])
    def get_sightings_json(self, start, end):
        return [
            sighting.get_detailed_json() for sighting in self.get_sightings()[start:end]
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

    def send_verify_account_email(self):
        code = self.get_email_confirmation_code()
        msg = Email(recipients=[self])
        verify_link = url_for(
            'api.auth_code_received',
            code_string_dot_json=code.accept_code,
            _external=True,
        )
        msg.template('misc/account_verify', verify_link=verify_link)
        msg.send_message()

    def set_password(self, password):
        if not password:
            # This function "sets" the password, it's the responsibility of the caller to ensure it's valid
            raise ValueError('Empty password not allowed')

        self.password = password
        with db.session.begin():
            db.session.merge(self)
        db.session.refresh(self)

        return self

    def lockout(self):
        from app.modules.auth.models import Code, OAuth2Client, OAuth2Grant, OAuth2Token

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
        ret_val = False

        if isinstance(obj, User):
            ret_val = obj == self

        # AssetGroup, Encounter, Project, Notification all have an owner field, check that
        if is_module_enabled('asset_groups'):
            from app.modules.asset_groups.models import AssetGroup

            if isinstance(obj, AssetGroup):
                ret_val = obj.owner == self

        if is_module_enabled('encounters'):
            from app.modules.encounters.models import Encounter

            if isinstance(obj, Encounter):
                ret_val = obj.owner == self

        if is_module_enabled('projects'):
            from app.modules.projects.models import Project

            if isinstance(obj, Project):
                ret_val = obj.owner == self

        if is_module_enabled('missions'):
            from app.modules.missions.models import (
                Mission,
                MissionCollection,
                MissionTask,
            )

            if isinstance(obj, (Mission, MissionCollection, MissionTask)):
                ret_val = obj.owner == self

        if is_module_enabled('notifications'):
            from app.modules.notifications.models import Notification

            if isinstance(obj, Notification):
                ret_val = obj.owner == self

        if is_module_enabled('assets'):
            from app.modules.assets.models import Asset

            if isinstance(obj, Asset):
                # assets are not owned directly by the user but the git store they're in is.
                # TODO: need to understand once assets become part of an encounter, do they still have a git store
                if obj.git_store is not None:
                    ret_val = obj.git_store.owner is self

        if is_module_enabled('sightings'):
            from app.modules.sightings.models import Sighting

            if isinstance(obj, Sighting):
                # decided (2021-03-12) that "owner" of a Sighting is not applicable therefore always False
                #   permissions must be handled in ways not dependent on ownership
                ret_val = False

        if is_module_enabled('individuals'):
            from app.modules.individuals.models import Individual

            if isinstance(obj, Individual):
                for encounter in obj.get_encounters():
                    if encounter.get_owner() is self:
                        ret_val = True
                        break

        return ret_val

    @module_required('encounters', 'annotations', resolve='warn', default=[])
    def get_my_annotations(self):
        annotations = []
        for encounter in self.owned_encounters:
            annotations.extend(encounter.annotations)
        return annotations

    @module_required('encounters', 'annotations', resolve='warn', default=[])
    def get_all_annotations(self):
        annotations = self.get_my_annotations()
        for collab_assoc in self.get_collaboration_associations():
            if collab_assoc.has_read():
                annotations.append(collab_assoc.get_other_user().get_my_annotations())

        return annotations

    def remove_profile_file(self):
        if self.profile_fileupload_guid:
            fup = self.profile_fileupload
            self.profile_fileupload_guid = None
            db.session.add(self)

            if fup:
                fup.delete()

    def deactivate(self):
        AuditLog.audit_log_object(log, self, 'Deactivating')
        # Store email hash for potential later restoration
        # But zap all of the personal information
        self.email = self._get_hashed_email(self.email)
        # But zap all of the personal information
        self.full_name = 'Inactivated User'
        self.is_active = False
        self.remove_profile_file()
        self.website = None
        self.forum_id = None

        self.password = security.generate_random(128)
        with db.session.begin():
            db.session.merge(self)

    def delete(self):
        for collab_assoc in self.get_collaboration_associations():
            collab_assoc.delete()
        for asset_group in self.get_asset_groups():
            asset_group.delete()

        with db.session.begin(subtransactions=True):
            # TODO: Ensure proper cleanup
            AuditLog.delete_object(log, self)
            db.session.delete(self)

    @classmethod
    def _get_hashed_email(cls, email):
        assert isinstance(email, str)
        hashed_email = hash(email.lower())
        return f'{hashed_email}@deactivated'

    @classmethod
    def get_deactivated_account(cls, email):
        hashed_email = cls._get_hashed_email(email)
        found_users = [user for user in User.query.all() if user.email == hashed_email]
        if found_users:
            return found_users[0]
        return None

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

    def is_public_user(self):
        return self.email == User.PUBLIC_USER_EMAIL

    @module_required('sightings', resolve='warn', default=[])
    def get_sightings(self):
        from app.modules.encounters.models import Encounter
        from app.modules.sightings.models import Sighting

        return (
            db.session.query(Sighting)
            .join(Encounter)
            .filter(Encounter.owner_guid == self.guid)
        ).all()

    # FIXME just stubbing out for email
    def get_preferred_langauge(self):
        return None


USER_ROLES = [
    role.value[-1]
    for role in User.StaticRoles.__members__.values()
    if role.value[-1] not in ('in_setup', 'in_reset', 'is_internal', 'is_staff')
]
