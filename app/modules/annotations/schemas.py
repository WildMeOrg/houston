# -*- coding: utf-8 -*-
"""
Serialization schemas for Annotations resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema
from app.modules import is_module_enabled
from .models import Annotation


class BaseAnnotationSchema(ModelSchema):
    """
    Base Annotation schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Annotation
        fields = (
            Annotation.guid.key,
            Annotation.asset_guid.key,
            Annotation.encounter_guid.key
            if is_module_enabled('encounters')
            else 'encounter_guid',
            Annotation.ia_class.key,
            Annotation.viewpoint.key,
            'elasticsearchable',
            Annotation.indexed.key,
        )
        dump_only = (Annotation.guid.key,)


class DetailedAnnotationSchema(BaseAnnotationSchema):
    """
    Detailed Annotation schema exposes all useful fields.
    """

    keywords = base_fields.Nested(
        'BaseKeywordSchema',
        many=True,
    )
    asset_src = base_fields.Function(Annotation.get_asset_src)

    class Meta(BaseAnnotationSchema.Meta):
        fields = BaseAnnotationSchema.Meta.fields + (
            Annotation.created.key,
            Annotation.updated.key,
            Annotation.bounds.key,
            'keywords',
            'asset_src',
        )
        dump_only = BaseAnnotationSchema.Meta.dump_only + (
            Annotation.created.key,
            Annotation.updated.key,
            'asset_src',
        )


class AnnotationElasticsearchSchema(BaseAnnotationSchema):
    """
    Schema for indexing by Elasticsearch

    Note: can be expensive (as it delves into related objects as well as EDM), so best not to use
    for purposes other than ES indexing.
    """

    keywords = base_fields.Function(Annotation.get_keyword_values)
    locationId = base_fields.Function(Annotation.get_location_id)
    taxonomy_guid = base_fields.Function(Annotation.get_taxonomy_guid)
    owner_guid = base_fields.Function(Annotation.get_owner_guid_str)
    encounter_guid = base_fields.Function(Annotation.get_encounter_guid_str)
    sighting_guid = base_fields.Function(Annotation.get_sighting_guid_str)
    time = base_fields.Function(Annotation.get_time_isoformat_in_timezone)

    class Meta(BaseAnnotationSchema.Meta):
        fields = BaseAnnotationSchema.Meta.fields + (
            Annotation.created.key,
            Annotation.updated.key,
            Annotation.bounds.key,
            Annotation.content_guid.key,
            'keywords',
            'locationId',
            'owner_guid',
            'taxonomy_guid',
            'encounter_guid',
            'sighting_guid',
            'time',
        )
        dump_only = BaseAnnotationSchema.Meta.dump_only + (
            Annotation.created.key,
            Annotation.updated.key,
        )
