# -*- coding: utf-8 -*-
"""
Common reusable Parameters classes
----------------------------------
"""

from flask_marshmallow import base_fields
from marshmallow import validate

from flask_restx_patched import Parameters


def _get_is_static_role_property(role_name, static_role):
    """
    A helper function that aims to provide a property getter and setter
    for static roles.

    Args:
        role_name (str)
        static_role (int) - a bit mask for a specific role

    Returns:
        property_method (property) - preconfigured getter and setter property
        for accessing role.
    """

    @property
    def _is_static_role_property(self):
        return self.has_static_role(static_role)

    @_is_static_role_property.setter
    def _is_static_role_property(self, value):
        if value:
            self.set_static_role(static_role)
        else:
            self.unset_static_role(static_role)

    _is_static_role_property.fget.__name__ = role_name
    return _is_static_role_property


class PaginationParameters(Parameters):
    """
    Helper Parameters class to reuse pagination.
    """

    search = base_fields.String(
        description='the field to filter the results by a search string',
        required=False,
    )
    limit = base_fields.Integer(
        description='limit a number of items (allowed range is 1-100)',
        missing=100,
        validate=validate.Range(min=1, max=100),
    )
    offset = base_fields.Integer(
        description='a number of items to skip',
        missing=0,
        validate=validate.Range(min=0),
    )
    sort = base_fields.String(
        description='the field to sort the results by, e.g. the primary key column',
        missing='primary',
    )
    reverse = base_fields.Boolean(
        description='the field to reverse the sorted results (before paging has been performed)',
        missing=False,
    )
    reverse_after = base_fields.Boolean(
        description='the field to reverse the sorted results (after paging has been performed)',
        missing=False,
    )


class PaginationParametersLatestFirst(PaginationParameters):

    sort = base_fields.String(
        description='the field to sort the results by, e.g. the created column',
        missing='created',
    )
    reverse = base_fields.Boolean(
        description='the field to reverse the sorted results (before paging has been performed)',
        missing=True,
    )
