# -*- coding: utf-8 -*-
"""
Serialization schemas for Missions resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema

from .models import Mission


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
        )
        dump_only = (Mission.guid.key,)


class DetailedMissionSchema(BaseMissionSchema):
    """
    Detailed Mission schema exposes all useful fields.
    """

    class Meta(BaseMissionSchema.Meta):
        fields = BaseMissionSchema.Meta.fields
        dump_only = BaseMissionSchema.Meta.dump_only
