# -*- coding: utf-8 -*-
"""
Encounters database models
--------------------
"""
import uuid
import logging

from app.extensions import db, FeatherModel
from app.modules import is_module_enabled
from app.modules.individuals.models import Individual
import app.extensions.logging as AuditLog


log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Encounter(db.Model, FeatherModel):
    """
    Encounters database model.
    """

    __mapper_args__ = {
        'confirm_deleted_rows': False,
    }

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    version = db.Column(db.BigInteger, default=None, nullable=True)

    sighting_guid = db.Column(
        db.GUID, db.ForeignKey('sighting.guid'), index=True, nullable=True
    )
    sighting = db.relationship('Sighting', back_populates='encounters')

    individual_guid = db.Column(
        db.GUID, db.ForeignKey('individual.guid'), index=True, nullable=True
    )
    individual = db.relationship('Individual', back_populates='encounters')

    owner_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=False
    )
    # owner = db.relationship(
    #     'User', back_populates='owned_encounters', foreign_keys=[owner_guid]
    # )
    owner = db.relationship(
        'User',
        backref=db.backref(
            'owned_encounters',
            primaryjoin='User.guid == Encounter.owner_guid',
            order_by='Encounter.guid',
        ),
        foreign_keys=[owner_guid],
    )

    submitter_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True
    )
    # submitter = db.relationship(
    #     'User', back_populates='submitted_encounters', foreign_keys=[submitter_guid]
    # )
    submitter = db.relationship(
        'User',
        backref=db.backref(
            'submitted_encounters',
            primaryjoin='User.guid == Encounter.submitter_guid',
            order_by='Encounter.guid',
        ),
        foreign_keys=[submitter_guid],
    )

    # Asset group sighting stores the configuration for this encounter,
    # Instead of duplicating the storage of it here, just store a reference into the structure
    # has to be nullable for db upgrade. Providing a default dummy guid would cause more problems
    # than it would solve
    asset_group_sighting_encounter_guid = db.Column(db.GUID, nullable=True)

    public = db.Column(db.Boolean, default=False, nullable=False)

    if is_module_enabled('encounters', 'projects'):
        # FIXME: MWS config is missing 'encounters' and 'projects' modules,
        #        but their relationship is loaded on runtime
        projects = db.relationship(
            'ProjectEncounter',
            back_populates='encounter',
            order_by='ProjectEncounter.project_guid',
        )

        annotations = db.relationship(
            'Annotation', back_populates='encounter', order_by='Annotation.guid'
        )

    time_guid = db.Column(
        db.GUID, db.ForeignKey('complex_date_time.guid'), index=True, nullable=True
    )
    time = db.relationship('ComplexDateTime')

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'version={self.version}, '
            'owner={self.owner},'
            'individual={self.individual_guid},'
            'sighting={self.sighting_guid},'
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def get_owner(self):
        return self.owner

    def get_sighting(self):
        return self.sighting

    def get_time_isoformat_in_timezone(self):
        return self.time.isoformat_in_timezone() if self.time else None

    def get_time_specificity(self):
        return self.time.specificity if self.time else None

    # this does the heavy lifting of trying to set time from user-provided data
    def set_time_from_data(self, data):
        if not data or 'time' not in data:
            return  # no need to try, time not being set
        from app.modules.complex_date_time.models import ComplexDateTime

        # will raise ValueError if data no good
        self.time = ComplexDateTime.from_data(data)

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

    def merge_request_hash(self):
        parts = [
            self.guid.int,
            # this covers weird cases where things arent persisted to db yet
            (self.owner and self.owner.guid or self.owner_guid).int,
            (self.individual and self.individual.guid or self.individual_guid).int,
        ]
        parts.sort()
        return hash(tuple(parts))

    def delete(self):
        AuditLog.delete_object(log, self)
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
        return response, response_data, result
