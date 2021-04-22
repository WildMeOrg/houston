# -*- coding: utf-8 -*-
"""
Serialization schemas for Asset_groups resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema

from .models import Submission


class BaseAssetGroupSchema(ModelSchema):
    """
    Base Asset_group schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Submission
        fields = (
            Submission.guid.key,
            Submission.commit.key,
            Submission.major_type.key,
            Submission.description.key,
        )
        dump_only = (
            Submission.guid.key,
            Submission.commit.key,
        )


class CreateAssetGroupSchema(BaseAssetGroupSchema):
    """
    Detailed Asset_group schema exposes all useful fields.
    """

    class Meta(BaseAssetGroupSchema.Meta):
        fields = BaseAssetGroupSchema.Meta.fields + (
            Submission.owner_guid.key,
            Submission.created.key,
            Submission.updated.key,
        )
        dump_only = BaseAssetGroupSchema.Meta.dump_only + (
            Submission.owner_guid.key,
            Submission.created.key,
            Submission.updated.key,
        )


class DetailedAssetGroupSchema(CreateAssetGroupSchema):
    """
    Detailed Asset_group schema exposes all useful fields.
    """

    from app.modules.assets.models import Asset

    assets = base_fields.Nested(
        'BaseAssetSchema',
        exclude=Asset.submission_guid.key,
        many=True,
    )

    class Meta(CreateAssetGroupSchema.Meta):
        fields = CreateAssetGroupSchema.Meta.fields + ('assets',)
        dump_only = CreateAssetGroupSchema.Meta.dump_only
