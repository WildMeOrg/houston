# -*- coding: utf-8 -*-
"""
Integrity database models
--------------------
"""

import uuid

from app.extensions import HoustonModel, db


class Integrity(db.Model, HoustonModel):
    """
    Integrity database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    # result data. Indexed on top level entity
    result = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def __init__(self):
        # Creating an Integrity entry runs the full integrity checks and generates and stores the result
        # for later analysis
        from app.modules.annotations.models import Annotation
        from app.modules.asset_groups.models import AssetGroup
        from app.modules.assets.models import Asset
        from app.modules.individuals.models import Individual
        from app.modules.sightings.models import Sighting

        self.result = {
            'asset_groups': AssetGroup.run_integrity(),
            'sightings': Sighting.run_integrity(),
            'individuals': Individual.run_integrity(),
            'annotations': Annotation.run_integrity(),
            'assets': Asset.run_integrity(),
        }

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.integrity.schemas import BaseIntegritySchema

        return BaseIntegritySchema
