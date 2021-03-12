# -*- coding: utf-8 -*-
"""
Sightings database models
--------------------
"""

from app.extensions import FeatherModel, db
import uuid
import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Sighting(db.Model, FeatherModel):
    """
    Sightings database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    version = db.Column(db.BigInteger, default=None, nullable=True)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def get_owners(self):
        owners = []
        for encounter in self.get_encounters():
            if encounter.get_owner() is not None and encounter.get_owner() not in owners:
                owners.append(encounter.get_owner())
        return owners

    def get_owner(self):
        # this is what we talked about but it makes me squeamish
        if self.get_owners() is not None:
            return self.get_owners()[0]
        return None

    def get_encounters(self):
        return self.encounters

    def add_encounter(self, encounter):
        if encounter not in self.encounters:
            self.encounters.append(encounter)

    def delete(self):
        with db.session.begin():
            db.session.delete(self)

    def delete_cascade(self):
        with db.session.begin(subtransactions=True):
            while self.encounters:
                enc = self.encounters.pop()
                enc.delete_cascade()
            db.session.delete(self)

    def delete_from_edm(self, current_app):
        response = current_app.edm.request_passthrough(
            'sighting.data',
            'delete',
            {},
            self.guid,
        )
        return response

    # given edm_json (verbose json from edm) will populate with houston-specific data from feather object
    # note: this modifies the passed in edm_json, so not sure how legit that is?
    def augment_edm_json(self, edm_json):
        if (self.encounters is not None and edm_json['encounters'] is None) or (
            self.encounters is None and edm_json['encounters'] is not None
        ):
            log.warning('Only one None encounters value between edm/feather objects!')
        if self.encounters is not None and edm_json['encounters'] is not None:
            if len(self.encounters) != len(edm_json['encounters']):
                log.warning('Imbalanced encounters between edm/feather objects!')
            else:
                i = 0
                while i < len(self.encounters):  # now we augment each encounter
                    self.encounters[i].augment_edm_json(edm_json['encounters'][i])
                    i += 1
        return edm_json
