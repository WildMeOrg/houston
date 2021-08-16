# -*- coding: utf-8 -*-
"""
Collaborations database models
--------------------
"""
import uuid
import logging
from flask_login import current_user

from app.extensions import db, HoustonModel
from app.modules.users.models import User


log = logging.getLogger(__name__)


class CollaborationUserState:
    ALLOWED_STATES = [
        'declined',
        'approved',
        'pending',
        'not_initiated',
        'revoked',
        'creator',
    ]
    DECLINED = ALLOWED_STATES[0]
    APPROVED = ALLOWED_STATES[1]
    PENDING = ALLOWED_STATES[2]
    NOT_INITIATED = ALLOWED_STATES[3]
    REVOKED = ALLOWED_STATES[4]
    CREATOR = ALLOWED_STATES[5]


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

        if initiator_states is not None and True not in initiator_states:
            # User manager created collaboration, store who the creator was
            collab_creator = CollaborationUserAssociations(
                collaboration=self, user=current_user
            )
            collab_creator.initiator = True
            collab_creator.read_approval_state = CollaborationUserState.CREATOR
            collab_creator.edit_approval_state = CollaborationUserState.CREATOR

    def _get_association_for_user(self, user_guid):
        assoc = None
        for association in self.collaboration_user_associations:
            if association.user_guid == user_guid:
                assoc = association
        return assoc

    def _get_association_for_other_user(self, user_guid):
        assoc = None
        if user_guid is not None:
            other_user_guids = [
                association.user_guid
                for association in self.collaboration_user_associations
                if (association.user_guid != user_guid)
                & (association.read_approval_state != CollaborationUserState.CREATOR)
            ]
            assert len(other_user_guids) == 1

            assoc = self._get_association_for_user(other_user_guids[0])
        return assoc

    def get_users(self):
        users = []
        for association in self.collaboration_user_associations:
            if association.read_approval_state != CollaborationUserState.CREATOR:
                users.append(association.user)
        return users

    def notify_pending_users(self):
        # Once created notify the pending user to accept
        for collab_user_assoc in self.collaboration_user_associations:
            if collab_user_assoc.read_approval_state == CollaborationUserState.PENDING:
                from app.modules.notifications.models import (
                    Notification,
                    NotificationType,
                )

                other_user_assoc = self._get_association_for_other_user(
                    collab_user_assoc.user.guid
                )
                data = {'requester': other_user_assoc.user_guid}
                Notification.create(
                    NotificationType.collab_request, collab_user_assoc.user, data
                )

    # todo remove, there is no overall view or edit state for the collaboration, it depends on the user
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

    def get_user_data_as_json(self):
        from app.modules.users.schemas import BaseUserSchema

        user_data = {}
        for association in self.collaboration_user_associations:
            assoc_data = BaseUserSchema().dump(association.user).data
            assoc_data['viewState'] = association.read_approval_state
            assoc_data['initiator'] = association.initiator
            user_data[str(association.user.guid)] = assoc_data

        return user_data

    def _is_new_read_approval_state_valid(self, old_state, new_state):
        ret_val = False
        # Only certain transitions are permitted
        if old_state == CollaborationUserState.NOT_INITIATED:
            ret_val = new_state != CollaborationUserState.CREATOR
        elif old_state == CollaborationUserState.PENDING:
            ret_val = new_state in [
                CollaborationUserState.APPROVED,
                CollaborationUserState.DECLINED,
            ]
        elif old_state == CollaborationUserState.APPROVED:
            ret_val = new_state == CollaborationUserState.REVOKED
        elif old_state == CollaborationUserState.DECLINED:
            ret_val = new_state == CollaborationUserState.APPROVED
        elif old_state == CollaborationUserState.REVOKED:
            ret_val = new_state == CollaborationUserState.APPROVED

        # Permit resetting to same state in all cases rather than handling separately for each
        if not ret_val:
            ret_val = old_state == new_state

        return ret_val

    def set_read_approval_state_for_user(self, user_guid, state):
        success = False
        if user_guid is not None and state in CollaborationUserState.ALLOWED_STATES:
            assert isinstance(user_guid, uuid.UUID)
            for association in self.collaboration_user_associations:
                if association.user_guid == user_guid:
                    if self._is_new_read_approval_state_valid(
                        association.read_approval_state, state
                    ):
                        association.read_approval_state = state
                        success = True
        return success

    def user_has_read_access(self, user_guid):
        ret_val = False
        assert isinstance(user_guid, uuid.UUID)

        other_assoc = self._get_association_for_other_user(user_guid)

        if other_assoc:
            ret_val = other_assoc.read_approval_state == CollaborationUserState.APPROVED

        return ret_val

    def set_edit_approval_state_for_user(self, user_guid, state):
        if user_guid is not None and state in CollaborationUserState.ALLOWED_STATES:
            assert isinstance(user_guid, uuid.UUID)
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
            assert isinstance(user_guid, uuid.UUID)
            for association in self.collaboration_user_associations:
                if association.user_guid == user_guid:
                    association.edit_approval_state = CollaborationUserState.APPROVED
                    association.initiator = True
                else:
                    association.edit_approval_state = CollaborationUserState.PENDING

    # This relates to if the user can access the collaboration itself, not the data
    def user_can_access(self, user):
        return user in self.get_users()

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def delete(self):
        with db.session.begin(subtransactions=True):
            for assoc in self.collaboration_user_associations:
                db.session.delete(assoc)
            db.session.delete(self)
