# -*- coding: utf-8 -*-
"""
Serialization schemas for Collaborations resources RESTful API
----------------------------------------------------
"""

# from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema
from flask_marshmallow import base_fields
from .models import Collaboration


class BaseCollaborationSchema(ModelSchema):
    """
    Base Collaboration schema exposes only the most general fields.
    """

    members = base_fields.Function(Collaboration.get_user_guids)
    read_state = base_fields.Function(Collaboration.get_read_state)
    edit_state = base_fields.Function(Collaboration.get_edit_state)

    class Meta:
        # pylint: disable=missing-docstring
        model = Collaboration
        fields = (
            Collaboration.guid.key,
            'members',
            'read_state',
            'edit_state',
        )
        dump_only = (Collaboration.guid.key,)


class DetailedCollaborationSchema(BaseCollaborationSchema):
    """
    Detailed Collaboration schema exposes all useful fields.
    """

    class Meta(BaseCollaborationSchema.Meta):
        fields = BaseCollaborationSchema.Meta.fields + (
            Collaboration.created.key,
            Collaboration.updated.key,
        )
        dump_only = BaseCollaborationSchema.Meta.dump_only + (
            Collaboration.created.key,
            Collaboration.updated.key,
        )
