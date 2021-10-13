# -*- coding: utf-8 -*-
"""
Relationships database models
--------------------
"""

from sqlalchemy_utils import Timestamp

from app.extensions import HoustonModel, db
from datetime import datetime  # NOQA

import uuid

import logging

log = logging.getLogger(__name__)


class RelationshipIndividualMember(db.Model, HoustonModel):
    relationship_guid = db.Column(
        db.GUID, db.ForeignKey('relationship.guid'), primary_key=True
    )
    relationship = db.relationship('Relationship', back_populates='individual_members')

    individual_guid = db.Column(
        db.GUID, db.ForeignKey('individual.guid'), primary_key=True
    )
    individual = db.relationship('Individual', back_populates='relationships')

    individual_role = db.Column(db.String, nullable=False)

    def __init__(self, individual, individual_role, **kwargs):
        self.individual = individual
        self.individual_role = individual_role
        self.individual_guid = individual.guid


class Relationship(db.Model, Timestamp):
    """
    Relationships database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    individual_members = db.relationship(
        'RelationshipIndividualMember', back_populates='relationship'
    )

    start_date = db.Column(
        db.DateTime, index=True, default=datetime.utcnow, nullable=True
    )
    end_date = db.Column(db.DateTime, index=True, default=datetime.utcnow, nullable=True)

    type = db.Column(db.String, nullable=True)

    def __init__(
        self, individual_1, individual_2, individual_1_role, individual_2_role, **kwargs
    ):
        if individual_1 and individual_2 and individual_1_role and individual_2_role:

            member_1 = RelationshipIndividualMember(individual_1, individual_1_role)
            member_2 = RelationshipIndividualMember(individual_2, individual_2_role)

            self.individual_members.append(member_1)
            self.individual_members.append(member_2)
        else:
            raise ValueError('Relationship needs two individuals, each with a role.')

    def has_individual(self, individual_guid):
        for individual_member in self.individual_members:
            if individual_member.individual_guid == individual_guid:
                return True
        return False

    def get_relationship_role_for_individual(self, individual_guid):
        if self.has_individual(individual_guid):
            for individual_member in self.individual_members:
                if individual_member.individual_guid is individual_guid:
                    return individual_member.individual_role
        return None

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )
