# -*- coding: utf-8 -*-
"""
Individuals database models
--------------------
"""

from app.extensions import FeatherModel, db
from flask import current_app
import uuid


class Individual(db.Model, FeatherModel):
    """
    Individuals database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    version = db.Column(db.BigInteger, default=None, nullable=True)

    encounters = db.relationship('Encounter', back_populates='individual')

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

            # If an individual has not been encountered, it does not exist
            # Although... I'm not satisfied with this. Auto delete only if the object is persisted? Hmm...
            # TODO Fix this
            # if len(self.encounters) == 0 and  Individual.query.get(self.guid) is not None:
            #     self.delete_from_edm(current_app)
            #     self.delete()

    def get_members(self):
        return [encounter.owner for encounter in self.encounters]

    def delete(self):
        with db.session.begin():
            db.session.delete(self)

    def delete_from_edm(self):
        response = current_app.edm.request_passthrough(
            'individual.data',
            'delete',
            {},
            self.guid,
        )
        return response
