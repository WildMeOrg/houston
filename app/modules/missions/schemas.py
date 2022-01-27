# -*- coding: utf-8 -*-
"""
Serialization schemas for Missions resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema
from flask_marshmallow import base_fields

from .models import Mission, MissionCollection, MissionTask


class BaseMissionSchema(ModelSchema):
    """
    Base Mission schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Mission
        fields = (
            Mission.guid.key,
            Mission.title.key,
            'created',
        )
        dump_only = (Mission.guid.key,)


class CreationMissionSchema(BaseMissionSchema):
    """
    Detailed Mission schema exposes all useful fields.
    """

    class Meta(BaseMissionSchema.Meta):
        fields = BaseMissionSchema.Meta.fields + (
            Mission.title.key,
            Mission.options.key,
            Mission.classifications.key,
            Mission.notes.key,
        )
        dump_only = BaseMissionSchema.Meta.dump_only


class DetailedMissionSchema(CreationMissionSchema):
    """
    Detailed Mission schema exposes all useful fields.
    """

    owner = base_fields.Nested('PublicUserSchema', many=False)

    assigned_users = base_fields.Nested('PublicUserSchema', many=True)

    class Meta(CreationMissionSchema.Meta):
        fields = CreationMissionSchema.Meta.fields + (
            'owner',
            'assigned_users',
        )
        dump_only = CreationMissionSchema.Meta.dump_only


class DetailedMissionJobSchema(ModelSchema):
    job_id = base_fields.String()
    active = base_fields.Boolean()
    start = base_fields.DateTime()


class BaseMissionCollectionSchema(ModelSchema):
    """
    Base Mission Collection schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = MissionCollection
        fields = (
            MissionCollection.guid.key,
            MissionCollection.commit.key,
            MissionCollection.major_type.key,
            MissionCollection.description.key,
        )
        dump_only = (
            MissionCollection.guid.key,
            MissionCollection.commit.key,
        )


class CreateMissionCollectionSchema(BaseMissionCollectionSchema):
    """
    Detailed Mission Collection schema exposes all useful fields.
    """

    class Meta(BaseMissionCollectionSchema.Meta):
        fields = BaseMissionCollectionSchema.Meta.fields + (
            MissionCollection.owner_guid.key,
            MissionCollection.created.key,
            MissionCollection.updated.key,
        )
        dump_only = BaseMissionCollectionSchema.Meta.dump_only + (
            MissionCollection.owner_guid.key,
            MissionCollection.created.key,
            MissionCollection.updated.key,
        )


class DetailedMissionCollectionSchema(CreateMissionCollectionSchema):
    """
    Detailed Mission Collection schema exposes all useful fields.
    """

    from app.modules.assets.models import Asset

    assets = base_fields.Nested(
        'BaseAssetSchema',
        # exclude=Asset.mission_collection_guid.key,
        many=True,
    )

    class Meta(CreateMissionCollectionSchema.Meta):
        fields = CreateMissionCollectionSchema.Meta.fields + ('assets',)
        dump_only = CreateMissionCollectionSchema.Meta.dump_only


class BaseMissionTaskSchema(ModelSchema):
    """
    Base MissionTask schema exposes only the most general fields.
    """

    mission = base_fields.Nested('BaseMissionSchema', many=False)

    class Meta:
        # pylint: disable=missing-docstring
        model = MissionTask
        fields = (
            MissionTask.guid.key,
            MissionTask.title.key,
            'mission',
        )
        dump_only = (MissionTask.guid.key,)


class DetailedMissionTaskSchema(BaseMissionTaskSchema):
    """
    Detailed MissionTask schema exposes all useful fields.
    """

    class Meta(BaseMissionTaskSchema.Meta):
        fields = BaseMissionTaskSchema.Meta.fields
        dump_only = BaseMissionTaskSchema.Meta.dump_only
