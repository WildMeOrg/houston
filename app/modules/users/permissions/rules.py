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


class WriteAccessRule(DenyAbortMixin, Rule):
    """
    Ensure that the current_user has has write access.
    """

    def check(self):
        return current_user.is_active


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

        # This Rule is for checking permissions on modules, so there must be one,
        assert self._module is not None

        if not current_user or current_user.is_anonymous:
            # Anonymous users can only create a submission
            has_permission = self._action == AccessOperation.WRITE and self._is_module(
                Submission
            )
        else:
            has_permission = (
                # inactive users can do nothing
                current_user.is_active
                & (
                    # staff and (currently) admin can do anything
                    current_user.is_staff
                    | current_user.is_admin
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
        from app.modules.projects.models import Project

        # Currently any user can do what they like. This is where the role specific access controls will be added
        has_permission = True
        if self._is_module(Project) and self._action is AccessOperation.READ:
            has_permission = user.is_admin | user.is_staff | user.is_internal

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

        if not current_user or current_user.is_anonymous:
            # Anonymous users can only read public objects
            has_permission = (
                self._action == AccessOperation.READ and self._obj.is_public()
            )
        else:
            has_permission = (
                # inactive users can do nothing
                current_user.is_active
                & (
                    # staff and (currently) admin can do anything
                    current_user.is_staff
                    | current_user.is_admin
                    | self._permitted_via_user(current_user)
                    | self._permitted_via_org(current_user)
                    | self._permitted_via_project(current_user)
                    | self._permitted_via_collaboration(current_user)
                )
            )
        return has_permission

    def _permitted_via_user(self, user):
        # users can read write and delete anything they own
        return user.owns_object(self._obj)

    def _permitted_via_org(self, user):
        has_permission = False
        # Orgs not supported fully yet, but allow read if user is in it
        if self._action == AccessOperation.READ:
            org_index = 0
            orgs = user.memberships
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
        projects = user.projects
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
                        for encounter in project.encounters:
                            # If time check was implemented, that would need to be passed here too and percolate down through
                            # encounters and sightings etc
                            # @todo should the functionality in encounters.has_read_permission move into rules.py
                            has_permission = encounter.has_read_permission(self._obj)
                project_index = project_index + 1
        elif self._action == AccessOperation.WRITE:
            # only power users can write
            has_permission = user.is_admin | user.is_staff | user.is_internal
        elif self._action == AccessOperation.DELETE:
            # or delete
            has_permission = user.is_admin | user.is_staff | user.is_internal
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


class StaffRoleRule(ActiveUserRoleRule):
    """
    Ensure that the current_user has an Admin role.
    """

    def check(self):
        return current_user.is_staff


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


class SupervisorRoleRule(ActiveUserRoleRule):
    """
    Ensure that the current_user has a Supervisor access to the given object.
    """

    def __init__(self, obj, **kwargs):
        super(SupervisorRoleRule, self).__init__(**kwargs)
        self._obj = obj

    def check(self):
        if not hasattr(self._obj, 'check_supervisor'):
            return False
        return self._obj.check_supervisor(current_user) is True


class OwnerRoleRule(ActiveUserRoleRule):
    """
    Ensure that the current_user has an Owner access to the given object.
    """

    def __init__(self, obj, **kwargs):
        super(OwnerRoleRule, self).__init__(**kwargs)
        self._obj = obj

    def check(self):
        if not hasattr(self._obj, 'check_owner'):
            return False
        return self._obj.check_owner(current_user) is True
