# -*- coding: utf-8 -*-
"""
Serialization schemas for Integrity resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema

from .models import Integrity


class BaseIntegritySchema(ModelSchema):
    """
    Base Integrity schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Integrity
        fields = (
            Integrity.guid.key,
            Integrity.title.key,
        )
        dump_only = (Integrity.guid.key,)


class DetailedIntegritySchema(BaseIntegritySchema):
    """
    Detailed Integrity schema exposes all useful fields.
    """

    class Meta(BaseIntegritySchema.Meta):
        fields = BaseIntegritySchema.Meta.fields + (
            Integrity.created.key,
            Integrity.updated.key,
        )
        dump_only = BaseIntegritySchema.Meta.dump_only + (
            Integrity.created.key,
            Integrity.updated.key,
        )
