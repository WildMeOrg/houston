# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods,invalid-name,abstract-method,method-hidden
"""
RESTful API Rules
-----------------------
"""
import logging

from flask_login import current_user
from flask_restplus._http import HTTPStatus
from permission import Rule as BaseRule
from typing import Type, Any
from app.extensions.api import abort
from app.modules.users.permissions.types import AccessOperation

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


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
            determine whether the current user has enough permissions to perform te action on the class.
        action (AccessRule) - can be READ, WRITE, DELETE
        """
        self._module = module
        self._action = action
        super().__init__(**kwargs)

    def check(self):
        from app.modules.submissions.models import Submission
        from app.modules.users.models import User
        from app.modules.encounters.models import Encounter

        # This Rule is for checking permissions on modules, so there must be one,
        assert self._module is not None

        # Anonymous users can create: a submission, encounter, [sighting,] or themselves
        if not current_user or current_user.is_anonymous:
            has_permission = False
            if self._action == AccessOperation.WRITE:
                has_permission = self._is_module((Submission, User, Encounter))
        else:
            has_permission = (
                # inactive users can do nothing
                current_user.is_active
                & self._can_user_perform_action(current_user)
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
        from app.extensions.config.models import HoustonConfig
        from app.modules.individuals.models import Individual
        from app.modules.submissions.models import Submission
        from app.modules.encounters.models import Encounter
        from app.modules.sightings.models import Sighting
        from app.modules.projects.models import Project
        from app.modules.assets.models import Asset
        from app.modules.users.models import User

        has_permission = False
        if user_is_privileged(user):
            # Organizations and Projects not supported for MVP, no-one can create them
            if not self._is_module((Organization, Project)):
                has_permission = True
        elif self._action is AccessOperation.READ:
            if user.is_admin:
                # This is where we can control what modules admin users can and cannot read
                # This could be Client configurable if required by taking the list passed to
                # _is_module from a config parameter e.g. app.config.get(ADMIN_READ_MODULE_PERMISSION)
                has_permission = self._is_module(User)
            if not has_permission and user.is_researcher:
                has_permission = self._is_module(
                    (Submission, Encounter, Sighting, Asset, Individual)
                )

        elif self._action is AccessOperation.WRITE:
            if self._is_module(HoustonConfig):
                has_permission = user.is_admin
            elif self._is_module((Submission, User)):
                # Any users can submit and write (create) a user
                has_permission = True
            elif self._is_module(Encounter):
                has_permission = True
            # Project disabled for MVP
            # elif self._is_module(Project):
            #     has_permission = user.is_researcher
            elif self._is_module(Individual):
                has_permission = user.is_researcher

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

    def check(self):
        # This Rule is for checking permissions on objects, so there must be one, Use the ModuleActionRule for
        # permissions checking without objects
        assert self._obj is not None

        # Anyone can read public data, even anonymous users
        has_permission = self._action == AccessOperation.READ and self._obj.is_public()

        if not has_permission and current_user and not current_user.is_anonymous:

            has_permission = (
                # inactive users can do nothing
                current_user.is_active
                & (
                    self._permitted_via_user(current_user)
                    # | self._permitted_via_org(current_user)
                    # | self._permitted_via_project(current_user)
                    | self._permitted_via_collaboration(current_user)
                )
            )
        return has_permission

    def _permitted_via_user(self, user):
        from app.modules.encounters.models import Encounter
        from app.modules.users.models import User

        # users can read write and delete anything they own while some users can do anything
        has_permission = owner_or_privileged(user, self._obj)

        if not has_permission and user.is_admin:
            # Admins can access all users
            if isinstance(self._obj, User):
                has_permission = True

        if not has_permission:
            # Projects and Orgs disabled for MVP
            #     # read and write access is permitted for any projects or organisations they're in
            #     # Details of what they're allowed to write handled in the patch parameters functionality
            #     # Region would be handled the same way here too
            #     if isinstance(self._obj, (Project, Organization)):
            #         has_permission = (
            #             user in self._obj.get_members()
            #             and self._action != AccessOperation.DELETE
            #         )

            if isinstance(self._obj, Encounter):
                # Researchers can read other encounters, only site admins can update and delete
                # them and those roles are not supported yet
                if self._action == AccessOperation.READ:
                    has_permission = user.is_researcher

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
        # @todo
        return False


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
def user_is_privileged(user):
    return user.is_staff or user.is_internal


def owner_or_privileged(user, obj):
    return user.owns_object(obj) or user_is_privileged(user)
