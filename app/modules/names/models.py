# -*- coding: utf-8 -*-
"""
Names database models
--------------------
"""
import uuid

from app.extensions import db, HoustonModel, Timestamp

# from app.modules.individuals.models import Individual
import logging
import app.extensions.logging as AuditLog

log = logging.getLogger(__name__)  # pylint: disable=invalid-name

# class NameUser(db.Model, HoustonModel):
# name_guid = db.Column(db.GUID, db.ForeignKey('name.guid'), primary_key=True)
# encounter_guid = db.Column(db.GUID, db.ForeignKey('encounter.guid'), primary_key=True)
# name = db.relationship('Name', back_populates='encounter_members')


class Name(db.Model, HoustonModel, Timestamp):
    """
    Names database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    value = db.Column(db.String(), index=True, nullable=False)

    context = db.Column(db.String(), index=True, nullable=False)

    individual_guid = db.Column(
        db.GUID, db.ForeignKey('individual.guid'), index=True, nullable=False
    )
    individual = db.relationship('Individual', back_populates='names')

    creator_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=False
    )
    creator = db.relationship(
        'User',
        backref=db.backref(
            'names_created',
            primaryjoin='User.guid == Name.creator_guid',
            order_by='Name.guid',
        ),
    )

    # this will ensure individual+context is unique (one context per individual)
    __table_args__ = (db.UniqueConstraint(context, individual_guid),)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            "context='{self.context}', "
            'value={self.value} '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def delete(self):
        AuditLog.delete_object(log, self, f'from {self.individual}')
        with db.session.begin():
            db.session.delete(self)
