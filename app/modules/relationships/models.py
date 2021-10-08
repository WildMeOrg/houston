# -*- coding: utf-8 -*-
"""
Relationships database models
--------------------
"""

from sqlalchemy_utils import Timestamp

from app.extensions import HoustonModel, db
from datetime import datetime  # NOQA

import uuid


class RelationshipIndividualMember(db.Model, HoustonModel):
    relationship_guid = db.Column(
        db.GUID, db.ForeignKey('relationship.guid'), primary_key=True
    )
    relationship = db.relationship(
        'Relationship', back_populates='individual_members'
    )

    individual_guid = db.Column(db.GUID, db.ForeignKey('individual.guid'), primary_key=True)
    individual = db.relationship('Individual', back_populates='relationships')



class Relationship(db.Model, Timestamp):
    """
    Relationships database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    # individual_1_role = db.Column(db.String, nullable=False)

    # individual_2_role = db.Column(db.String, nullable=False)

    individual_members = db.relationship(
        'RelationshipIndividualMember', back_populates='relationship'
    )

    start_date = db.Column(db.DateTime, index=True, default=datetime.utcnow, nullable=True)
    end_date = db.Column(db.DateTime, index=True, default=datetime.utcnow, nullable=True)

    def __init__(self, individual_1, individual_2, individual_1_role, individual_2_role, **kwargs):
        self.individual_1 = individual_1
        self.individual_2 = individual_2
        self.individual_1_role = individual_1_role
        self.individual_2_role = individual_2_role


    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'individual_1_guid={self.individual_1_guid}, '
            'individual_2_guid={self.individual_2_guid}, '
            'individual_1_role={self.individual_1_role}, '
            'individual_2_role={self.individual_2_role}, '
            ')>'.format(
                class_name=self.__class__.__name__,
                self=self
            )
        )
