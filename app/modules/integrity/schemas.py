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
            Integrity.created.key,
            Integrity.result.key,
            'elasticsearchable',
            Integrity.indexed.key,
        )
        dump_only = (Integrity.guid.key,)
