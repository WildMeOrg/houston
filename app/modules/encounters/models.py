# -*- coding: utf-8 -*-
"""
Encounters database models
--------------------
"""

from app.extensions import db, FeatherModel
from app.modules.individuals.models import Individual

from app.modules.asset_groups import models as asset_groups_models  # NOQA
from app.modules.assets import models as assets_models  # NOQA


import uuid


class Encounter(db.Model, FeatherModel):
    """
    Encounters database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    version = db.Column(db.BigInteger, default=None, nullable=True)

    from app.modules.sightings.models import Sighting

    sighting_guid = db.Column(
        db.GUID, db.ForeignKey('sighting.guid'), index=True, nullable=True
    )
    sighting = db.relationship('Sighting', backref=db.backref('encounters'))

    from app.modules.individuals.models import Individual

    individual_guid = db.Column(
        db.GUID, db.ForeignKey('individual.guid'), index=True, nullable=True
    )
    individual = db.relationship('Individual', backref=db.backref('encounters'))

    owner_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=False
    )
    owner = db.relationship(
        'User', backref=db.backref('owned_encounters'), foreign_keys=[owner_guid]
    )

    submitter_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True
    )
    submitter = db.relationship(
        'User', backref=db.backref('submitted_encounters'), foreign_keys=[submitter_guid]
    )

    public = db.Column(db.Boolean, default=False, nullable=False)

    projects = db.relationship('ProjectEncounter', back_populates='encounter')

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'version={self.version}, '
            'owner={self.owner},'
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def get_owner(self):
        return self.owner

    def get_sighting(self):
        return self.sighting

    # not going to check for ownership by User.get_public_user() because:
    #  a) this allows for other-user-owned data to be toggled to public
    #  b) allows for us to _disallow_ public access to public-user-owned data
    def set_individual(self, individual):
        if isinstance(individual, Individual):
            self.individual = individual

    def is_public(self):
        return self.public

    def add_annotation(self, annotation):
        if annotation not in self.annotations:
            with db.session.begin(subtransactions=True):
                self.annotations.append(annotation)

    def delete(self):
        with db.session.begin():
            db.session.delete(self)

    def delete_cascade(self):
        with db.session.begin(subtransactions=True):
            db.session.delete(self)

    def delete_from_edm(self, current_app, request):
        (response, response_data, result,) = current_app.edm.request_passthrough_parsed(
            'encounter.data',
            'delete',
            {},
            self.guid,
            request_headers=request.headers,
        )
        return (response, response_data, result)

    def augment_edm_json(self, edm_json):
        edm_json['createdHouston'] = self.created.isoformat()
        edm_json['updatedHouston'] = self.updated.isoformat()
        from app.modules.users.schemas import PublicUserSchema

        user_schema = PublicUserSchema(many=False)
        json, err = user_schema.dump(self.get_owner())
        edm_json['owner'] = json
        if self.submitter_guid is not None:
            json, err = user_schema.dump(self.submitter)
            edm_json['submitter'] = json
        return edm_json
