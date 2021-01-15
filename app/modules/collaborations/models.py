# -*- coding: utf-8 -*-
"""
Collaborations database models
--------------------
"""
import uuid

from app.extensions import db, HoustonModel


class CollaborationUserAssociations(db.Model, HoustonModel):
    """
    Collaboration many to many association with Users.
    Should be a maximum of two per Collaboration.
    """

    collaboration_guid = db.Column(
        db.GUID, db.ForeignKey('collaboration.guid'), primary_key=True
    )
    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), primary_key=True)

    collaboration = db.relationship(
        'Collaboration', back_populates='collaboration_user_associations'
    )
    user = db.relationship('User', back_populates='user_collaboration_associations')


class CollaborationStates():
    DECLINED = 'declined'
    APPROVED = 'approved'
    PENDING = 'pending'


class CollaborationLevels():
    READ = 'read'
    EDIT = 'edit'


class Collaboration(db.Model, HoustonModel):
    """
    Collaborations database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    title = db.Column(db.String(length=50), nullable=False)

    collaboration_user_associations = db.relationship(
        'CollaborationUserAssociations', back_populates='collaboration'
    )

    state = db.Column(db.String(length=32), default=CollaborationStates.PENDING, nullable=False)

    def __init__(self, *args, **kwargs):
        if 'users' not in kwargs or len(kwargs.get('users') != 2):
            raise ValueError('Collaboration initialization must have two users.')
        super().__init__(*args, **kwargs)


    def get_users(self):
        users = []
        for association in self.collaboration_user_associations:
            users.append(association.user)
        return users


    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'users={self.get_users}, '
            "title='{self.title}'"
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @db.validates('title')
    def validate_title(self, key, title):  # pylint: disable=unused-argument,no-self-use
        if len(title) < 3:
            raise ValueError('Title has to be at least 3 characters long.')
        return title
