# -*- coding: utf-8 -*-
"""
￼Serialization schemas for Annotations resources RESTful API
￼----------------------------------------------------
￼"""

from flask_marshmallow import base_fields

from flask_restx_patched import ModelSchema

from .models import ScoutAnnotation


class BaseAnnotationSchema(ModelSchema):
    """
         Base Annotation schema exposes only the most general fields.
    ￼"""

    class Meta:
        # pylint: disable=missing-docstring
        model = ScoutAnnotation
        fields = (
            ScoutAnnotation.guid.key,
            ScoutAnnotation.asset_guid.key,
            ScoutAnnotation.ia_class.key,
            ScoutAnnotation.viewpoint.key,
            'elasticsearchable',
            ScoutAnnotation.indexed.key,
        )
        dump_only = (ScoutAnnotation.guid.key,)


class DetailedAnnotationSchema(BaseAnnotationSchema):
    """
    ￼    Detailed Annotation schema exposes all useful fields.
    ￼"""

    keywords = base_fields.Nested(
        'BaseKeywordSchema',
        many=True,
    )
    asset_src = base_fields.Function(lambda ann: ann.get_asset_src())

    class Meta(BaseAnnotationSchema.Meta):
        fields = BaseAnnotationSchema.Meta.fields + (
            ScoutAnnotation.created.key,
            ScoutAnnotation.updated.key,
            ScoutAnnotation.bounds.key,
            ScoutAnnotation.task_guid.key,
            'keywords',
            'asset_src',
        )
        dump_only = BaseAnnotationSchema.Meta.dump_only + (
            ScoutAnnotation.created.key,
            ScoutAnnotation.updated.key,
            'asset_src',
        )


class AnnotationElasticsearchSchema(BaseAnnotationSchema):
    """
    ￼    Schema for indexing by Elasticsearch
    ￼
    ￼    Note: can be expensive (as it delves into related objects), so best not to use
    ￼    for purposes other than ES indexing.
    ￼"""

    keywords = base_fields.Function(lambda ann: ann.get_keyword_values())

    class Meta(BaseAnnotationSchema.Meta):
        fields = BaseAnnotationSchema.Meta.fields + (
            ScoutAnnotation.created.key,
            ScoutAnnotation.updated.key,
            ScoutAnnotation.bounds.key,
            ScoutAnnotation.content_guid.key,
            'keywords',
        )
        dump_only = BaseAnnotationSchema.Meta.dump_only + (
            ScoutAnnotation.created.key,
            ScoutAnnotation.updated.key,
        )
