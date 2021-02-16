# -*- coding: utf-8 -*-
"""
Individuals database models
--------------------
"""

from app.extensions import FeatherModel, db

import uuid


class Individual(db.Model, FeatherModel):
    """
    Individuals database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def get_encounters(self):
        return self.encounters

    def add_encounters(self, encounters):
        for encounter in encounters:
            if encounter not in self.get_encounters():
                self.encounters.append(encounter)

    def add_encounter(self, encounter):
        self.add_encounters([encounter])

    def remove_encounter(self, encounter):
        if encounter in self.get_encounters():
            self.encounters.remove(encounter)

    def get_members(self):
        return [encounter.owner for encounter in self.encounters]
