# -*- coding: utf-8 -*-
"""
Collaborations database models
--------------------
"""
import uuid
import logging

from app.extensions import db, HoustonModel
from app.modules.users.models import User


log = logging.getLogger(__name__)


class CollaborationUserState:
    ALLOWED_STATES = ['declined', 'approved', 'pending', 'not_initiated', 'revoked']
    DECLINED = ALLOWED_STATES[0]
    APPROVED = ALLOWED_STATES[1]
    PENDING = ALLOWED_STATES[2]
    NOT_INITIATED = ALLOWED_STATES[3]
    REVOKED = ALLOWED_STATES[4]


class CollaborationUserAssociations(db.Model, HoustonModel):
    """
    Collaboration many to many association with Users.
    Current maximum of two users per Collaboration.
    """

    collaboration_guid = db.Column(
        db.GUID, db.ForeignKey('collaboration.guid'), default=uuid.uuid4, primary_key=True
    )
    collaboration = db.relationship(
        'Collaboration', back_populates='collaboration_user_associations'
    )

    user = db.relationship('User', back_populates='user_collaboration_associations')
    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), primary_key=True)

    initiator = db.Column(db.Boolean, default=False, nullable=False)
    read_approval_state = db.Column(
        db.String(length=32), default=CollaborationUserState.PENDING, nullable=False
    )
    edit_approval_state = db.Column(
        db.String(length=32), default=CollaborationUserState.NOT_INITIATED, nullable=False
    )


class Collaboration(db.Model, HoustonModel):
    """
    Collaborations database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    title = db.Column(db.String(length=50), nullable=True)

    collaboration_user_associations = db.relationship(
        'CollaborationUserAssociations', back_populates='collaboration'
    )

    def __init__(
        self, user_guids=None, approval_states=None, initiator_states=None, **kwargs
    ):
        # I think this can be adapted to allow >2 User collabs, opening the door for Org-level.
        if user_guids is None or len(user_guids) != 2:
            raise ValueError(
                '__init__ Collaboration: Creating a collaboration requires a user_guids list.'
            )

        # You can create a collaboration where both users 'approved'
        if approval_states is not None and len(approval_states) != len(user_guids):
            raise ValueError(
                '__init__ Collaboration: Length of approval_states was not equal to provided user list.'
            )

        if initiator_states is not None and len(initiator_states) != len(user_guids):
            raise ValueError(
                '__init__ Collaboration: Length of initiator_states states was not equal to provided user list.'
            )

        for guid_index in range(len(user_guids)):
            user_tup = User.ensure_edm_obj(user_guids[guid_index])

            if user_tup is None or user_tup[0] is None:
                raise ValueError(
                    '__init__ Collaboration: One of the user_guids provided had no associated user.'
                )

            collab_user_assoc = CollaborationUserAssociations(
                collaboration=self, user=user_tup[0]
            )

            if (
                approval_states is not None
                and approval_states[guid_index] in CollaborationUserState.ALLOWED_STATES
            ):
                collab_user_assoc.read_approval_state = approval_states[guid_index]
            if (
                initiator_states is not None
                and isinstance(initiator_states[guid_index], bool)
                and initiator_states[guid_index] is True
            ):
                collab_user_assoc.initiator = initiator_states[guid_index]
                # If you initiate you approve
                collab_user_assoc.read_approval_state = CollaborationUserState.APPROVED

    def get_users(self):
        users = []
        for association in self.collaboration_user_associations:
            users.append(association.user)
        return users

    def get_user_guids(self):
        return [
            association.user.guid for association in self.collaboration_user_associations
        ]

    def get_initiators(self):
        users = []
        for association in self.collaboration_user_associations:
            if association.initiator is True:
                users.append(association.user)
        return users

    def get_read_state(self):
        read_state = None  # if you return this the collaboration is corrupt
        for association in self.collaboration_user_associations:
            if association.read_approval_state == CollaborationUserState.DECLINED:
                # only one user need decline
                read_state = CollaborationUserState.DECLINED
                break
            elif association.read_approval_state == CollaborationUserState.PENDING:
                # only one user needs pending, but we should still keep looking for declined
                read_state = CollaborationUserState.PENDING
            elif (
                association.read_approval_state == CollaborationUserState.APPROVED
                and read_state is None
            ):
                # every association must approve to return approved, everything else overrides it
                read_state = CollaborationUserState.APPROVED
        return read_state

    def get_edit_state(self):
        edit_state = None
        for association in self.collaboration_user_associations:
            # 'not_initiated' should never coexist with other states on a collaboration
            if association.edit_approval_state == CollaborationUserState.DECLINED:
                edit_state = CollaborationUserState.DECLINED
                break
            elif association.edit_approval_state == CollaborationUserState.NOT_INITIATED:
                edit_state = CollaborationUserState.NOT_INITIATED
                break
            elif association.edit_approval_state == CollaborationUserState.PENDING:
                edit_state = CollaborationUserState.PENDING
            elif (
                association.read_approval_state == CollaborationUserState.APPROVED
                and edit_state is None
            ):
                edit_state = CollaborationUserState.APPROVED
        return edit_state

    def set_read_approval_state_for_user(self, user_guid, state):
        if user_guid is not None and state in CollaborationUserState.ALLOWED_STATES:
            for association in self.collaboration_user_associations:
                if association.user_guid == user_guid:
                    association.read_approval_state = state

    def set_edit_approval_state_for_user(self, user_guid, state):
        if user_guid is not None and state in CollaborationUserState.ALLOWED_STATES:
            # if one association is edit level NOT_INITIATED, they all are
            if (
                self.get_edit_state() == CollaborationUserState.NOT_INITIATED
                and state is not CollaborationUserState.NOT_INITIATED
            ):
                self.initate_edit_with_user(user_guid)
            for association in self.collaboration_user_associations:
                if (
                    association.user_guid == user_guid
                    or state == CollaborationUserState.NOT_INITIATED
                ):
                    association.edit_approval_state = state

    def initate_edit_with_user(self, user_guid):
        if user_guid is not None:
            for association in self.collaboration_user_associations:
                if association.user_guid == user_guid:
                    association.edit_approval_state = CollaborationUserState.APPROVED
                    association.initiator = True
                else:
                    association.edit_approval_state = CollaborationUserState.PENDING

    def user_can_access(self, user):
        return user in self.get_users()

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            "title='{self.title}' "
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @db.validates('title')
    def validate_title(self, key, title):  # pylint: disable=unused-argument,no-self-use
        if len(title) < 3:
            raise ValueError('Title has to be at least 3 characters long.')
        return title

    def delete(self):
        with db.session.begin(subtransactions=True):
            for assoc in self.collaboration_user_associations:
                db.session.delete(assoc)
            db.session.delete(self)
