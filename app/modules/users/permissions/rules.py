# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods,invalid-name,abstract-method,method-hidden
"""
RESTful API Rules
-----------------------
"""
from flask_login import current_user
from flask_restplus._http import HTTPStatus
from permission import Rule as BaseRule
from typing import Type, Any
from app.extensions.api import abort
from app.modules.users.permissions.types import AccessOperation


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

        # This Rule is for checking permissions on modules, so there must be one,
        assert self._module is not None

        # Anonymous users can only create a submission or themselves
        if not current_user or current_user.is_anonymous:
            has_permission = False
            if self._action == AccessOperation.WRITE:
                has_permission = self._is_module(Submission) or self._is_module(User)
        else:
            has_permission = (
                # inactive users can do nothing
                current_user.is_active
                & (
                    # some users can do anything
                    user_is_privileged(current_user, self._module)
                    | self._can_user_perform_action(current_user)
                )
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
        from app.modules.submissions.models import Submission
        from app.modules.projects.models import Project
        from app.modules.users.models import User

        has_permission = False

        if self._action is AccessOperation.READ:
            has_permission = self._user_is_privileged(user)
        elif self._action is AccessOperation.WRITE:
            if self._is_module(Submission):
                # Any users can submit
                has_permission = True
            if self._is_module(User):
                # And modify users apparently?
                has_permission = True
            elif self._is_module(Project):
                has_permission = user.is_researcher

        return has_permission

    def _user_is_privileged(self, user):
        # This is where we can control what operations admin users can and cannot perform.
        # This could be project configurable as required
        from app.extensions.config.models import HoustonConfig

        # An example for now is that admin users are not allowed to change the config, only staff
        if self._is_module(HoustonConfig):
            ret_val = user.is_staff | user.is_internal
        else:
            ret_val = user.is_admin | user.is_staff | user.is_internal
        return ret_val


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
                    # some users can do anything
                    user_is_privileged(current_user, self._obj)
                    | self._permitted_via_user(current_user)
                    | self._permitted_via_org(current_user)
                    | self._permitted_via_project(current_user)
                    | self._permitted_via_collaboration(current_user)
                )
            )
        return has_permission

    def _permitted_via_user(self, user):
        from app.modules.organizations.models import Organization
        from app.modules.projects.models import Project

        # users can read write and delete anything they own
        has_permission = user.owns_object(self._obj)

        if not has_permission:
            # read and write access is permitted for any projects or organisations they're in
            # Details of what they're allowed to write handled in the patch parameters functionality
            # Region would be handled the same way here too
            if isinstance(self._obj, Project) or isinstance(self._obj, Organization):
                has_permission = (
                    user in self._obj.get_members()
                    and self._action != AccessOperation.DELETE
                )

        return has_permission

    def _permitted_via_org(self, user):
        has_permission = False
        # Orgs not supported fully yet, but allow read if user is in it
        if self._action == AccessOperation.READ:
            org_index = 0
            orgs = user.get_org_memberships()
            while not has_permission and org_index < len(orgs):
                org = orgs[org_index]
                member_index = 0
                while not has_permission and member_index < len(org.members):
                    has_permission = org.members[member_index].owns_object(self._obj)
                    member_index = member_index + 1
                org_index = org_index + 1

        return has_permission

    def _permitted_via_project(self, user):
        from app.modules.encounters.models import Encounter

        has_permission = False
        project_index = 0
        projects = user.get_projects()
        # @todo role based access to the project and the objects in it
        if self._action == AccessOperation.READ:
            while not has_permission and project_index < len(projects):
                project = projects[project_index]
                has_permission = project == self._obj
                if not has_permission:
                    if isinstance(self._obj, Encounter):
                        # Optionally add time check so that User can only access encounters after user was added to project
                        has_permission = self._obj in project.encounters
                    else:
                        for encounter in project.get_encounters():
                            # If time check was implemented, that would need to be passed here too and percolate down through
                            # encounters and sightings etc
                            # @todo should the functionality in encounters.has_read_permission move into rules.py
                            has_permission = encounter.has_read_permission(self._obj)
                project_index = project_index + 1
        elif self._action == AccessOperation.WRITE:
            # only power users can write
            has_permission = user_is_privileged(user, self._obj)
        elif self._action == AccessOperation.DELETE:
            # or delete
            has_permission = user_is_privileged(user, self._obj)
        return has_permission

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


# Helper to have one place that defines what users are privileged, to potentially make it
# configurable depending upon customer and the object they're trying to access
def user_is_privileged(user, obj):
    return user.is_staff or user.is_admin
