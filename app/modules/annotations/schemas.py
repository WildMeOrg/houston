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


# utility for other methods below (caches data on annot so only needs to fetch once)
def get_enc(annot):
    if hasattr(annot, '_enc'):
        return annot._enc, annot._enc_edm, annot._sight_edm
    if not annot.encounter_guid:
        return None, None, None
    from app.modules.encounters.models import Encounter
    from flask import current_app

    annot._enc = Encounter.query.get(annot.encounter_guid)
    annot._enc_edm = current_app.edm.get_dict(
        'encounter.data_complete', annot.encounter_guid
    ).get('result')
    annot._sight_edm = current_app.edm.get_dict(
        'sighting.data_complete', annot._enc.sighting_guid
    ).get('result')
    return annot._enc, annot._enc_edm, annot._sight_edm


def get_locationId(annot):
    enc, enc_edm, sight_edm = get_enc(annot)
    if not enc or not enc_edm or not sight_edm:
        return None
    return enc_edm.get('locationId') or sight_edm.get('locationId')


def get_taxonomy_guid(annot):
    enc, enc_edm, sight_edm = get_enc(annot)
    if not enc or not enc_edm:
        return None
    return enc_edm.get('taxonomy')


def get_time(annot):
    enc, enc_edm, sight_edm = get_enc(annot)
    if not enc:
        return None
    return enc.get_time_isoformat_in_timezone(sighting_fallback=True)


def get_owner_guid(annot):
    enc, enc_edm, sight_edm = get_enc(annot)
    if not enc:
        return None
    return str(enc.owner_guid)


def get_keywords_flat(annot):
    if not annot.keyword_refs:
        return []
    return sorted([ref.keyword.value for ref in annot.keyword_refs])


class AnnotationElasticsearchSchema(BaseAnnotationSchema):
    """
    Schema for indexing by Elasticsearch

    Note: can be expensive (as it delves into related objects as well as EDM), so best not to use
    for purposes other than ES indexing.
    """

    keywords = base_fields.Function(get_keywords_flat)
    locationId = base_fields.Function(get_locationId)
    taxonomy_guid = base_fields.Function(get_taxonomy_guid)
    owner_guid = base_fields.Function(get_owner_guid)
    time = base_fields.Function(get_time)

    class Meta(BaseAnnotationSchema.Meta):
        fields = BaseAnnotationSchema.Meta.fields + (
            Annotation.created.key,
            Annotation.updated.key,
            Annotation.bounds.key,
            'keywords',
            'locationId',
            'owner_guid',
            'taxonomy_guid',
            'time',
        )
        dump_only = BaseAnnotationSchema.Meta.dump_only + (
            Annotation.created.key,
            Annotation.updated.key,
        )
