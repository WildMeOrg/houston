# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods,invalid-name,abstract-method,method-hidden
"""
RESTful API permissions
-----------------------
"""

import logging

from flask_sqlalchemy import BaseQuery
from permission import Permission as BasePermission

from app.modules.users.permissions.types import AccessOperation

from . import rules

log = logging.getLogger(__name__)


class PermissionExtendedQuery(BaseQuery):
    """
    Extends BaseQuery class from flask_sqlalchemy to add get_or_403 method

    Example:
    >>> DataTransformation.query.get_or_403(id)
    """

    def __init__(self, permission, *args, **kwargs):
        super(PermissionExtendedQuery, self).__init__(*args, **kwargs)
        self.permission = permission

    def get_or_403(self, ident):
        obj = self.get_or_404(ident)
        with self.permission(obj=obj):
            return obj


class Permission(BasePermission):
    """
    Declares classmethod to provide extended BaseQuery to model,
    which adds additional method get_or_403
    """

    @classmethod
    def get_query_class(cls):
        """
        Returns extended BaseQuery class for flask_sqlalchemy model to provide get_or_403 method

        Example:
        >>> DataTransformation(db.Model):
        ...     query_class = OwnerRolePermission.get_query_class()
        """
        return lambda *args, **kwargs: PermissionExtendedQuery(cls, *args, **kwargs)


class PasswordRequiredPermissionMixin(object):
    """
    Helper rule mixin that ensure that user password is correct if
    `password_required` is set to True.
    """

    def __init__(self, password_required=False, password=None, **kwargs):
        # NOTE: kwargs is required since it is a mixin
        """
        Args:
            password_required (bool) - in some cases you may need to ask
                users for a password to allow certain actions, enforce this
                requirement by setting this :bool:`True`.
            password (str) - pass a user-specified password here.
        """
        self._password_required = password_required
        self._password = password
        super(PasswordRequiredPermissionMixin, self).__init__(**kwargs)

    def rule(self):
        _rule = super(PasswordRequiredPermissionMixin, self).rule()
        if self._password_required:
            _rule &= rules.PasswordRequiredRule(self._password)
        return _rule


class ModuleAccessPermission(Permission):
    """
    Ensure that the current user has sufficient permission to perform the action on the object
    """

    def __init__(self, module=None, action=AccessOperation.READ, **kwargs):
        """
        Args:
        module (class) - any class can be passed here, this functionality will determine
             whether the current user has enough permissions to perform the action on the class.
        action (ObjectAccessOperation) - READ, WRITE, DELETE supported
        """
        self._module = module
        self._action = action
        super().__init__(**kwargs)

    def rule(self):
        return rules.ModuleActionRule(self._module, self._action)


class ObjectAccessPermission(Permission):
    """
    Ensure that the current user has sufficient permission to perform the action on the object
    """

    def __init__(self, obj=None, action=AccessOperation.READ, **kwargs):
        """
        Args:
        obj (object) - any object can be passed here, this functionality will determine
             whether the current user has enough permissions to perform the action on the object.
        action (ObjectAccessOperation) - READ, WRITE, DELETE supported
        """
        self._obj = obj
        self._action = action
        super().__init__(**kwargs)

    def rule(self):
        return rules.ObjectActionRule(self._obj, self._action)


class ModuleOrObjectAccessPermission(Permission):
    """
    Ensure that the current user has sufficient permission to perform the action on the object
    """

    def __init__(self, module=None, obj=None, action=AccessOperation.READ, **kwargs):
        """
        Args:
        module (class) - any class can be passed here, this functionality will determine
             whether the current user has enough permissions to perform the action on the class.
        obj (object) - any object can be passed here, this functionality will determine
             whether the current user has enough permissions to perform the action on the object.
        action (ObjectAccessOperation) - READ, WRITE, DELETE supported
        """
        self._module = module
        self._obj = obj
        self._action = action
        super().__init__(**kwargs)

    def rule(self):
        return rules.ModuleOrObjectActionRule(self._module, self._obj, self._action)


class RolePermission(Permission):
    """
    This class aims to help distinguish all role-type permissions.
    """

    def __init__(self, partial=False, **kwargs):
        """
        Args:
            partial (bool) - True values is mostly useful for Swagger
                documentation purposes.
        """
        self._partial = partial
        super(RolePermission, self).__init__(**kwargs)

    def rule(self):
        if self._partial:
            return rules.PartialPermissionDeniedRule()
        return rules.AllowAllRule()


class ActiveUserRolePermission(RolePermission):
    """
    This resource requires an active logged in user session
    """

    def rule(self):
        return rules.ActiveUserRoleRule()


class AdminRolePermission(PasswordRequiredPermissionMixin, RolePermission):
    """
    This resource requires an active logged in user session, and the user must have ALL of following roles: Admin
    """

    def rule(self):
        return rules.InternalRoleRule() | (
            rules.AdminRoleRule() & super(AdminRolePermission, self).rule()
        )
