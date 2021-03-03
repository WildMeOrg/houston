# -*- coding: utf-8 -*-
"""
Serialization schemas for Sightings resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema

from .models import Sighting


class BaseSightingSchema(ModelSchema):
    """
    Base Sighting schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Sighting
        fields = (
            Sighting.guid.key,
            Sighting.title.key,
        )
        dump_only = (Sighting.guid.key,)


class DetailedSightingSchema(BaseSightingSchema):
    """
    Detailed Sighting schema exposes all useful fields.
    """

    class Meta(BaseSightingSchema.Meta):
        fields = BaseSightingSchema.Meta.fields + (
            Sighting.created.key,
            Sighting.updated.key,
        )
        dump_only = BaseSightingSchema.Meta.dump_only + (
            Sighting.created.key,
            Sighting.updated.key,
        )
