# -*- coding: utf-8 -*-
"""
Serialization schemas for Individuals resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema

from .models import Individual


class BaseIndividualSchema(ModelSchema):
    """
    Base Individual schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Individual
        fields = (Individual.guid.key,)
        dump_only = (Individual.guid.key,)


class DetailedIndividualSchema(BaseIndividualSchema):
    """
    Detailed Individual schema exposes all useful fields.
    """

    class Meta(BaseIndividualSchema.Meta):
        fields = BaseIndividualSchema.Meta.fields + (
            Individual.created.key,
            Individual.updated.key,
        )
        dump_only = BaseIndividualSchema.Meta.dump_only + (
            Individual.created.key,
            Individual.updated.key,
        )
