# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods,invalid-name,abstract-method,method-hidden
"""
RESTful API Rules
-----------------------
"""
import logging

from flask_login import current_user
from flask_restx_patched._http import HTTPStatus
from permission import Rule as BaseRule
from typing import Type, Any
from app.extensions.api import abort
from app.modules.users.permissions.types import AccessOperation

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


# Map of user permissions on the module. This only applies to real users, anonymous users must be handled separately
MODULE_USER_MAP = {
    ('SiteSetting', AccessOperation.READ): ['is_admin'],
    ('SiteSetting', AccessOperation.WRITE): ['is_admin'],
    ('HoustonConfig', AccessOperation.WRITE): ['is_admin'],
    ('Asset', AccessOperation.READ): ['is_admin'],
    ('AssetGroup', AccessOperation.READ): ['is_admin'],
    ('AssetGroup', AccessOperation.WRITE): ['is_active'],
    ('Encounter', AccessOperation.READ): ['is_researcher'],
    ('Encounter', AccessOperation.WRITE): ['is_active'],  # TODO is this still correct
    ('Sighting', AccessOperation.READ): ['is_researcher'],
    ('Sighting', AccessOperation.WRITE): ['is_active'],
    ('Individual', AccessOperation.READ): ['is_researcher'],
    ('Individual', AccessOperation.WRITE): ['is_researcher'],
    ('Annotation', AccessOperation.READ): ['is_researcher'],
    ('Annotation', AccessOperation.WRITE): ['is_researcher'],
    ('User', AccessOperation.READ): ['is_user_manager'],
    ('User', AccessOperation.WRITE): ['is_active'],  # Creating yourself
    # Any user can request to collaborate with anyone
    ('Collaboration', AccessOperation.WRITE): ['is_active'],
    ('Collaboration', AccessOperation.READ): ['is_user_manager'],
    ('Notification', AccessOperation.READ): ['is_active'],
    ('Keyword', AccessOperation.READ): ['is_active'],
    ('Keyword', AccessOperation.WRITE): ['is_active'],
    ('AuditLog', AccessOperation.READ): ['is_researcher'],
    ('AuditLog', AccessOperation.READ_PRIVILEGED): ['is_admin'],
    ('SocialGroup', AccessOperation.READ): ['is_researcher'],
    ('SocialGroup', AccessOperation.WRITE): ['is_researcher'],
}

# Map of user permissions on the object. These permissions are not granted by collaboration
OBJECT_USER_MAP = {
    ('SiteSetting', AccessOperation.WRITE): ['is_admin'],
    ('SiteSetting', AccessOperation.DELETE): ['is_admin'],
    ('AssetGroupSighting', AccessOperation.READ): [
        'is_admin',
        'is_researcher',
    ],
    ('AssetGroupSighting', AccessOperation.WRITE): [
        'is_admin',
        'is_researcher',
    ],
    ('AssetGroupSighting', AccessOperation.WRITE_PRIVILEGED): ['is_internal'],
    ('Encounter', AccessOperation.READ): ['is_researcher'],
    ('Individual', AccessOperation.READ): ['is_researcher'],
    ('User', AccessOperation.WRITE): [
        'is_user_manager',
        'is_admin',
    ],
    ('User', AccessOperation.DELETE): [
        'is_user_manager',
        'is_admin',
    ],
    ('User', AccessOperation.READ): [
        'is_user_manager',
        'is_admin',
    ],
    ('Keyword', AccessOperation.READ): ['is_active'],
    ('Sighting', AccessOperation.WRITE_PRIVILEGED): ['is_internal'],
    ('SocialGroup', AccessOperation.READ): ['is_researcher'],
    ('SocialGroup', AccessOperation.WRITE): ['is_researcher'],
    ('SocialGroup', AccessOperation.DELETE): ['is_researcher'],
}

# Map of methods (that are passed he current user as a param) on the object.
# These permissions also granted by collaboration/project/etc so must not be privileged/admin
OBJECT_USER_METHOD_MAP = {
    ('Sighting', AccessOperation.READ): ['user_is_owner'],
    ('Sighting', AccessOperation.WRITE): ['user_owns_all_encounters'],
    ('Sighting', AccessOperation.DELETE): ['user_can_edit_all_encounters'],
    ('Asset', AccessOperation.READ_PRIVILEGED): ['user_raw_read'],
    ('Asset', AccessOperation.WRITE): ['user_is_owner'],
    ('Annotation', AccessOperation.READ): ['user_is_owner'],
    ('Annotation', AccessOperation.WRITE): ['user_is_owner'],
    ('Annotation', AccessOperation.DELETE): ['user_is_owner'],
    ('Collaboration', AccessOperation.READ): ['user_can_access'],
    ('Collaboration', AccessOperation.WRITE): ['user_can_access'],
}


class DenyAbortMixin(object):
    """
    A helper permissions mixin raising an HTTP Error (specified in
    ``DENY_ABORT_CODE``) on deny.

    NOTE: Apply this mixin before Rule class so it can override NotImplemented
    deny method.
    """

    DENY_ABORT_HTTP_CODE = HTTPStatus.FORBIDDEN
    DENY_ABORT_MESSAGE = None

    def deny(self):
        """
        Abort HTTP request by raising HTTP error exception with a specified
        HTTP code.
        """
        return abort(code=self.DENY_ABORT_HTTP_CODE, message=self.DENY_ABORT_MESSAGE)


class Rule(BaseRule):
    """
    Experimental base Rule class that helps to automatically handle inherited
    rules.
    """

    def base(self):
        # XXX: it handles only the first appropriate Rule base class
        # TODO: PR this case to permission project
        for base_class in self.__class__.__bases__:
            if issubclass(base_class, Rule):
                if base_class in {Rule, BaseRule}:
                    continue
                return base_class()
        return None


class AllowAllRule(Rule):
    """
    Helper rule that always grants access.
    """

    def check(self):
        return True


class ModuleActionRule(DenyAbortMixin, Rule):
    """
    Ensure that the current_user has has permission to perform the action on the module passed.
    """

    def __init__(self, module=None, action=AccessOperation.READ, **kwargs):
        """
        Args:
        module (Class) - any class can be passed here, which this functionality will
            determine whether the current user has enough permissions to perform the action on the class.
        action (AccessRule) - can be READ, WRITE, DELETE
        """
        self._module = module
        self._action = action
        super().__init__(**kwargs)

    def check(self):
        from app.modules.asset_groups.models import AssetGroup
        from app.modules.users.models import User
        from app.modules.encounters.models import Encounter
        from app.modules.sightings.models import Sighting

        # This Rule is for checking permissions on modules, so there must be one,
        assert self._module is not None
        has_permission = False
        if not current_user or current_user.is_anonymous:
            if self._action == AccessOperation.WRITE:
                has_permission = self._is_module((AssetGroup, User, Encounter, Sighting))
        else:
            roles = MODULE_USER_MAP.get((self._module.__name__, self._action))
            if roles:
                for role in roles:
                    if hasattr(current_user, role):
                        if getattr(current_user, role):
                            has_permission = True

            if not has_permission:
                has_permission = (
                    # inactive users can do nothing
                    current_user.is_active
                    & self._can_user_perform_action(current_user)
                )
        if not has_permission:
            log.debug(
                'Access permission denied for %r on %r by %r'
                % (self._action, self._module, current_user)
            )
        return has_permission

    # Helper to identify what the module is
    def _is_module(self, cls: Type[Any]):
        try:
            return issubclass(self._module, cls)
        except TypeError:
            return False

    # Permissions control entry point for real users, for all objects and all operations
    def _can_user_perform_action(self, user):
        from app.modules.organizations.models import Organization
        from app.modules.projects.models import Project

        has_permission = False

        if user.is_privileged:
            # Organizations and Projects not supported for MVP, no-one can create them
            if not self._is_module((Organization, Project)):
                has_permission = True

        return has_permission


class ObjectActionRule(DenyAbortMixin, Rule):
    """
    Ensure that the current_user has has permission to perform the action on the object passed.
    """

    def __init__(self, obj=None, action=AccessOperation.READ, **kwargs):
        """
        Args:
        obj (object) - any object can be passed here, which this functionality will
            determine whether the current user has enough permissions to write given object
            object.
        action (AccessRule) - can be READ, WRITE, DELETE
        """
        self._obj = obj
        self._action = action
        super().__init__(**kwargs)

    def any_table_driven_permission(self):
        roles = OBJECT_USER_MAP.get((self._obj.__class__.__name__, self._action))

        object_user_methods = OBJECT_USER_METHOD_MAP.get(
            (self._obj.__class__.__name__, self._action)
        )

        if roles is None and object_user_methods is None:
            return False, False

        if roles is not None:
            for role in roles:
                if not hasattr(current_user, role):
                    log.warning(f'user object does not have accessor {role}')
                elif getattr(current_user, role):
                    return True, True

        if object_user_methods is not None:
            for method in object_user_methods:
                if not hasattr(self._obj, method):
                    log.warning(
                        f'{self._obj.__class__.__name__} object does not have accessor {method}'
                    )
                elif getattr(self._obj, method)(current_user):
                    return True, True

        return True, False

    def elevated_permission(self, user):
        if (
            self._action == AccessOperation.READ_PRIVILEGED
            or self._action == AccessOperation.WRITE_PRIVILEGED
        ):
            return False
        else:
            return owner_or_privileged(user, self._obj)

    def check(self):
        # This Rule is for checking permissions on objects, so there must be one, Use the ModuleActionRule for
        # permissions checking without objects
        assert self._obj is not None
        # Anyone can read public data, even anonymous and inactive users
        has_permission = self._action == AccessOperation.READ and self._obj.is_public()

        if current_user and not current_user.is_anonymous and current_user.is_active:
            if not has_permission:
                was_table_driven, has_permission = self.any_table_driven_permission()

            if not has_permission:
                has_permission = self.elevated_permission(current_user) | (
                    self._permitted_via_collaboration(current_user)
                    # | self._permitted_via_org(current_user)
                    # | self._permitted_via_project(current_user)
                )

        if not has_permission:
            log.info(
                'Access permission denied for %r, %r by %r'
                % (self._action, self._obj, current_user)
            )
        return has_permission

    # def _permitted_via_org(self, user):
    #     has_permission = False
    #     # Orgs not supported fully yet, but allow read if user is in it
    #     if self._action == AccessOperation.READ:
    #         org_index = 0
    #         orgs = user.get_org_memberships()
    #         while not has_permission and org_index < len(orgs):
    #             org = orgs[org_index]
    #             member_index = 0
    #             org_members = org.get_members()
    #             while not has_permission and member_index < len(org_members):
    #                 has_permission = org_members[member_index].owns_object(self._obj)
    #                 member_index = member_index + 1
    #             org_index = org_index + 1
    #
    #     return has_permission

    # def _permitted_via_project(self, user):
    #     from app.modules.encounters.models import Encounter
    #     from app.modules.assets.models import Asset
    #
    #     has_permission = False
    #     project_index = 0
    #     projects = user.get_projects()
    #     # For MVP, Project ownership/membership is the driving factor for access to data within the project,
    #     # not the Role. If Role specific access is later required, it would be added here.
    #     # A user may read an object via permission granted via the project. The user may not update or
    #     # delete an object through permissions granted via their access to the object through the project.
    #     if self._action == AccessOperation.READ:
    #         while not has_permission and project_index < len(projects):
    #             project = projects[project_index]
    #             has_permission = project == self._obj
    #             if not has_permission:
    #                 if isinstance(self._obj, Encounter):
    #                     # Optionally add time check so that User can only access encounters after user was added to project
    #                     has_permission = self._obj in project.get_encounters()
    #                 elif isinstance(self._obj, Asset):
    #                     for encounter in project.get_encounters():
    #                         has_permission = self._obj in encounter.get_assets()
    #             project_index = project_index + 1

    def _permitted_via_collaboration(self, user):
        from app.modules.collaborations.models import CollaborationUserState

        tried_users = [user]
        object_user_methods = OBJECT_USER_METHOD_MAP.get(
            (self._obj.__class__.__name__, self._action)
        )

        for collab_assoc in user.user_collaboration_associations:
            if collab_assoc.read_approval_state != CollaborationUserState.CREATOR:
                collab_users = collab_assoc.collaboration.get_users()
                for other_user in collab_users:
                    if other_user not in tried_users:
                        tried_users.append(other_user)

                        if other_user.owns_object(self._obj):
                            if (
                                self._action == AccessOperation.READ
                            ) & collab_assoc.collaboration.user_has_read_access(
                                current_user.guid
                            ):
                                return True
                            elif (
                                self._action == AccessOperation.WRITE
                            ) & collab_assoc.collaboration.user_has_edit_access(
                                current_user.guid
                            ):
                                return True
                            break

                    if object_user_methods is not None:
                        for method in object_user_methods:
                            if not hasattr(self._obj, method):
                                log.warning(
                                    f'{self._obj.__class__.__name__} object does not have accessor {method}'
                                )
                            elif getattr(self._obj, method)(other_user):
                                return True

        return False


# Some modules are special (AssetGroups) mad may require both access controls in one
class ModuleOrObjectActionRule(DenyAbortMixin, Rule):
    def __init__(self, module=None, obj=None, action=AccessOperation.READ, **kwargs):
        """
        Args:
        obj (object) - any object can be passed here, which this functionality will
            determine whether the current user has enough permissions to write given object
            object.
        module (Class) - any class can be passed here, which this functionality will
            determine whether the current user has enough permissions to perform the action on the class.
        action (AccessRule) - can be READ, WRITE, DELETE
        """
        self._obj = obj
        self._action = action
        self._module = module
        super().__init__(**kwargs)

    def check(self):
        from app.modules.asset_groups.models import AssetGroup

        has_permission = False
        assert self._obj is not None or self._module is not None
        if self._obj:
            has_permission = ObjectActionRule(self._obj, self._action).check()
        else:
            if self._module == AssetGroup:
                # Read in this case equates to learn that the asset_group exists on gitlab,
                # Delete is to allow the researcher to know that it's on gitlab but not local
                if (
                    self._action == AccessOperation.READ
                    or self._action == AccessOperation.DELETE
                ):
                    has_permission = current_user.is_researcher
                # Write equates to allowing the cloning of the asset_group from gitlab
                elif self._action == AccessOperation.WRITE:
                    has_permission = current_user.is_admin

        return has_permission


class ActiveUserRoleRule(DenyAbortMixin, Rule):
    """
    Ensure that the current_user is activated.
    """

    def check(self):
        # Do not override DENY_ABORT_HTTP_CODE because inherited classes will
        # better use HTTP 403/Forbidden code on denial.
        self.DENY_ABORT_HTTP_CODE = HTTPStatus.UNAUTHORIZED
        # NOTE: `is_active` implies `is_authenticated`.
        return current_user.is_active


class PasswordRequiredRule(DenyAbortMixin, Rule):
    """
    Ensure that the current user has provided a correct password.
    """

    def __init__(self, password, **kwargs):
        super(PasswordRequiredRule, self).__init__(**kwargs)
        self._password = password

    def check(self):
        return current_user.password == self._password


class AdminRoleRule(ActiveUserRoleRule):
    """
    Ensure that the current_user has an Admin role.
    """

    def check(self):
        return current_user.is_admin


class InternalRoleRule(ActiveUserRoleRule):
    """
    Ensure that the current_user has an Internal role.
    """

    def check(self):
        return current_user.is_internal


class PartialPermissionDeniedRule(Rule):
    """
    Helper rule that must fail on every check since it should never be checked.
    """

    def check(self):
        raise RuntimeError('Partial permissions are not intended to be checked')


# Helpers to have one place that defines what users are privileged in all cases
def owner_or_privileged(user, obj):
    return user.owns_object(obj) or user.is_privileged
