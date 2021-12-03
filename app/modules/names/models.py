# -*- coding: utf-8 -*-
"""
Names database models
--------------------
"""
import uuid

from app.extensions import db, HoustonModel, Timestamp

import logging
import app.extensions.logging as AuditLog

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class NamePreferringUsersJoin(db.Model, HoustonModel):
    name_guid = db.Column(
        db.GUID, db.ForeignKey('name.guid', ondelete='CASCADE'), primary_key=True
    )
    user_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid', ondelete='CASCADE'), primary_key=True
    )
    name = db.relationship('Name', back_populates='preferring_user_joins')
    user = db.relationship('User')


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

    preferring_user_joins = db.relationship(
        'NamePreferringUsersJoin', back_populates='name'
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

    def get_preferring_users(self):
        return [join.user for join in self.preferring_user_joins]

    def add_preferring_user(self, user):
        if user in self.get_preferring_users():
            raise ValueError(f'{user} already in list')
        pref_join = NamePreferringUsersJoin(name_guid=self.guid, user_guid=user.guid)
        with db.session.begin():
            db.session.add(pref_join)

    def remove_preferring_user(self, user):
        found = None
        for pref_join in self.preferring_user_joins:
            if pref_join.user_guid == user.guid:
                found = pref_join
        if found:
            with db.session.begin():
                db.session.delete(found)

    def delete(self):
        AuditLog.delete_object(log, self, f'from Individual {self.individual.guid}')
        with db.session.begin(subtransactions=True):
            for join in self.preferring_user_joins:
                db.session.delete(join)
            db.session.delete(self)
