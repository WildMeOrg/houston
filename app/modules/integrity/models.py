# -*- coding: utf-8 -*-
"""
Integrity database models
--------------------
"""

from app.extensions import db, HoustonModel

import uuid


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
        from app.modules.sightings.models import Sighting
        from app.modules.encounters.models import Encounter

        self.result['sightings'] = Sighting.run_integrity()
        self.result['encounters'] = Encounter.run_integrity()
