# -*- coding: utf-8 -*-
"""
Serialization schemas for Assets resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields

from app.extensions.git_store import GitStore
from flask_restx_patched import ModelSchema


class BaseGitStoreSchema(ModelSchema):
    """
    Base Git Store schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = GitStore
        fields = (
            GitStore.guid.key,
            GitStore.commit.key,
            GitStore.major_type.key,
            GitStore.description.key,
            'elasticsearchable',
            GitStore.indexed.key,
        )
        dump_only = (
            GitStore.guid.key,
            GitStore.commit.key,
        )


class CreateGitStoreSchema(BaseGitStoreSchema):
    """
    Detailed Git Store schema exposes all useful fields.
    """

    class Meta(BaseGitStoreSchema.Meta):
        fields = BaseGitStoreSchema.Meta.fields + (
            GitStore.owner_guid.key,
            GitStore.created.key,
            GitStore.updated.key,
        )
        dump_only = BaseGitStoreSchema.Meta.dump_only + (
            GitStore.owner_guid.key,
            GitStore.created.key,
            GitStore.updated.key,
        )


class DetailedGitStoreSchema(CreateGitStoreSchema):
    """
    Detailed Git Store schema exposes all useful fields.
    """

    from app.modules.assets.models import Asset

    assets = base_fields.Nested(
        'BaseAssetSchema',
        exclude=Asset.git_store_guid.key,
        many=True,
    )

    class Meta(CreateGitStoreSchema.Meta):
        fields = CreateGitStoreSchema.Meta.fields + ('assets',)
        dump_only = CreateGitStoreSchema.Meta.dump_only
