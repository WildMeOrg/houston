# -*- coding: utf-8 -*-
"""
Collaborations database models
--------------------
"""
import uuid
import logging
from flask_login import current_user

from app.extensions import db, HoustonModel
import app.extensions.logging as AuditLog
from app.utils import HoustonException


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

    __mapper_args__ = {
        'confirm_deleted_rows': False,
    }

    collaboration_guid = db.Column(
        db.GUID, db.ForeignKey('collaboration.guid'), default=uuid.uuid4, primary_key=True
    )
    collaboration = db.relationship(
        'Collaboration', back_populates='collaboration_user_associations'
    )

    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), primary_key=True)

    user = db.relationship('User', backref=db.backref('user_collaboration_associations'))

    read_approval_state = db.Column(
        db.String(length=32), default=CollaborationUserState.PENDING, nullable=False
    )
    edit_approval_state = db.Column(
        db.String(length=32), default=CollaborationUserState.NOT_INITIATED, nullable=False
    )

    def delete(self):
        self.collaboration.user_deleted(self)

    def has_read(self):
        return self.collaboration.user_has_read_access(self.user_guid)

    def has_edit(self):
        return self.collaboration.user_has_edit_access(self.user_guid)

    def get_other_user(self):
        return self.collaboration.get_other_user(self.user_guid)


class Collaboration(db.Model, HoustonModel):
    """
    Collaborations database model.
    """

    __mapper_args__ = {
        'confirm_deleted_rows': False,
    }

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    collaboration_user_associations = db.relationship(
        'CollaborationUserAssociations', back_populates='collaboration'
    )
    initiator_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=False
    )
    init_req_notification_guid = db.Column(
        db.GUID, db.ForeignKey('notification.guid'), nullable=True
    )
    edit_initiator_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True
    )
    edit_req_notification_guid = db.Column(
        db.GUID, db.ForeignKey('notification.guid'), nullable=True
    )

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.collaborations.schemas import DetailedCollaborationSchema

        return DetailedCollaborationSchema

    def __init__(self, members, initiator_user, notify_users=True, **kwargs):

        num_users = len(members)
        if num_users != 2:
            raise ValueError('Creating a collaboration requires 2 members.')
        if not hasattr(initiator_user, 'is_user_manager'):
            # current user is not actually a User although it quacks like one so can't use isinstance
            raise ValueError(f'initiator_user {initiator_user} is not a user')

        # user manager created are handled differently
        manager_created = initiator_user not in members
        if manager_created and not initiator_user.is_user_manager:
            raise ValueError(
                f'Attempted creation of a collaboration by a non manager {initiator_user.email}.'
            )

        self.initiator_guid = initiator_user.guid
        self.edit_initiator_guid = None

        for user in members:
            if not hasattr(user, 'is_user_manager'):
                raise ValueError(f'User {user} is not a user manager')

            collab_user_assoc = CollaborationUserAssociations(
                collaboration=self, user=user
            )

            # Edit not enabled on creation
            collab_user_assoc.edit_approval_state = CollaborationUserState.NOT_INITIATED
            with db.session.begin(subtransactions=True):
                db.session.add(collab_user_assoc)

            # If you initiate, then you approve read. Manager created are also read approved
            if user == initiator_user or manager_created:
                collab_user_assoc.read_approval_state = CollaborationUserState.APPROVED
            else:
                collab_user_assoc.read_approval_state = CollaborationUserState.PENDING

        if notify_users and not manager_created:
            self.notify_pending_users()

        if manager_created:

            # User manager created collaboration, store who the creator was
            collab_creator = CollaborationUserAssociations(
                collaboration=self, user=initiator_user
            )
            from app.modules.notifications.models import NotificationType

            collab_creator.read_approval_state = CollaborationUserState.CREATOR
            collab_creator.edit_approval_state = CollaborationUserState.CREATOR
            if notify_users:
                for user in members:
                    user_assoc = self._get_association_for_user(user.guid)
                    self._notify_user(
                        collab_creator, user_assoc, NotificationType.collab_manager_create
                    )
            with db.session.begin(subtransactions=True):
                db.session.add(collab_creator)

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

    # note: returns manager *of this collaboration* (if applicable).  this user
    #   may no longer be an active manager (role).
    def get_manager(self):
        for association in self.collaboration_user_associations:
            if association.read_approval_state == CollaborationUserState.CREATOR:
                return association.user
        return None

    def get_users(self):
        users = []
        for association in self.collaboration_user_associations:
            if association.read_approval_state != CollaborationUserState.CREATOR:
                users.append(association.user)
        return users

    def user_guids(self):
        user_guids = []
        for association in self.collaboration_user_associations:
            if association.read_approval_state != CollaborationUserState.CREATOR:
                user_guids.append(association.user_guid)
        return user_guids

    def notify_pending_users(self):
        # Once created notify the pending user to accept
        for collab_user_assoc in self.collaboration_user_associations:

            if (
                collab_user_assoc.read_approval_state == CollaborationUserState.PENDING
                or collab_user_assoc.edit_approval_state == CollaborationUserState.PENDING
            ):
                from app.modules.notifications.models import NotificationType

                other_user_assoc = self._get_association_for_other_user(
                    collab_user_assoc.user.guid
                )

                if (
                    collab_user_assoc.read_approval_state
                    == CollaborationUserState.PENDING
                ):
                    self._notify_user(
                        other_user_assoc,
                        collab_user_assoc,
                        NotificationType.collab_request,
                    )

                if (
                    collab_user_assoc.edit_approval_state
                    == CollaborationUserState.PENDING
                ):
                    self._notify_user(
                        other_user_assoc,
                        collab_user_assoc,
                        NotificationType.collab_edit_request,
                    )

    def _notify_user(self, sending_user_assoc, receiving_user_assoc, notification_type):
        from app.modules.notifications.models import (
            Notification,
            NotificationBuilder,
            NotificationType,
        )

        builder = NotificationBuilder(sending_user_assoc.user)
        builder.set_collaboration(self)
        notif = Notification.create(notification_type, receiving_user_assoc.user, builder)

        # in these states, every notification is considered to have been read/resolved
        fully_resolved_notification_states = {
            NotificationType.collab_edit_approved,
            NotificationType.collab_edit_revoke,
            NotificationType.collab_revoke,
        }

        if notification_type is NotificationType.collab_request:
            self.init_req_notification_guid = notif.guid
        elif notification_type is NotificationType.collab_edit_request:
            self.edit_req_notification_guid = notif.guid

        # set necessary notification.is_resolved fields
        elif notification_type is NotificationType.collab_approved:
            if self.init_req_notification_guid:
                Notification.resolve(self.init_req_notification_guid)
        elif notification_type in fully_resolved_notification_states:
            if self.init_req_notification_guid:
                Notification.resolve(self.init_req_notification_guid)
            if self.edit_req_notification_guid:
                Notification.resolve(self.edit_req_notification_guid)

    def get_user_data_as_json(self):
        from app.modules.users.schemas import BaseUserSchema

        user_data = {}
        for association in self.collaboration_user_associations:
            if association.read_approval_state == CollaborationUserState.CREATOR:
                continue
            assoc_data = BaseUserSchema().dump(association.user).data
            assoc_data['viewState'] = association.read_approval_state
            assoc_data['editState'] = association.edit_approval_state
            user_data[str(association.user.guid)] = assoc_data

        return user_data

    def _is_approval_state_transition_valid(self, old_state, new_state):
        ret_val = False
        # Only certain transitions are permitted
        if old_state == CollaborationUserState.NOT_INITIATED:
            ret_val = new_state in [
                CollaborationUserState.CREATOR,
                CollaborationUserState.APPROVED,
                CollaborationUserState.PENDING,
            ]
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
        if state not in CollaborationUserState.ALLOWED_STATES:
            raise ValueError(
                f'State "{state}" not in allowed states: {", ".join(CollaborationUserState.ALLOWED_STATES)}'
            )
        if user_guid is not None:
            assert isinstance(user_guid, uuid.UUID)
            for association in self.collaboration_user_associations:
                if association.user_guid == user_guid:
                    if self._is_approval_state_transition_valid(
                        association.read_approval_state, state
                    ):
                        association.read_approval_state = state
                        # If a user revokes view and previously allowed edit, they automatically
                        # revoke edit too
                        if (
                            state == CollaborationUserState.REVOKED
                            and association.edit_approval_state
                            == CollaborationUserState.APPROVED
                        ):

                            association.edit_approval_state = state

                        from app.modules.notifications.models import NotificationType

                        if state == CollaborationUserState.REVOKED:
                            self._notify_user(
                                association,
                                self._get_association_for_other_user(user_guid),
                                NotificationType.collab_revoke,
                            )
                        elif state == CollaborationUserState.APPROVED:
                            self._notify_user(
                                association,
                                self._get_association_for_other_user(user_guid),
                                NotificationType.collab_approved,
                            )
                        with db.session.begin(subtransactions=True):
                            db.session.merge(association)
                        success = True
        return success

    def user_has_read_access(self, user_guid):
        ret_val = False
        assert isinstance(user_guid, uuid.UUID)

        my_assoc = self._get_association_for_user(user_guid)
        other_assoc = self._get_association_for_other_user(user_guid)

        if my_assoc and other_assoc:
            ret_val = (
                my_assoc.read_approval_state == CollaborationUserState.APPROVED
                and other_assoc.read_approval_state == CollaborationUserState.APPROVED
            )

        return ret_val

    def user_has_edit_access(self, user_guid):
        ret_val = False
        assert isinstance(user_guid, uuid.UUID)

        my_assoc = self._get_association_for_user(user_guid)
        other_assoc = self._get_association_for_other_user(user_guid)

        if my_assoc and other_assoc:
            ret_val = (
                my_assoc.edit_approval_state == CollaborationUserState.APPROVED
                and other_assoc.edit_approval_state == CollaborationUserState.APPROVED
            )
        return ret_val

    def get_other_user(self, user_guid):
        other_assoc = self._get_association_for_other_user(user_guid)
        if other_assoc:
            return other_assoc.user
        return None

    def set_edit_approval_state_for_user(self, user_guid, state):
        success = False
        if state not in CollaborationUserState.ALLOWED_STATES:
            raise ValueError(
                f'State "{state}" not in allowed states: {", ".join(CollaborationUserState.ALLOWED_STATES)}'
            )
        if user_guid is not None:
            assert isinstance(user_guid, uuid.UUID)
            for association in self.collaboration_user_associations:
                if association.user_guid == user_guid:
                    if self._is_approval_state_transition_valid(
                        association.edit_approval_state, state
                    ):
                        association.edit_approval_state = state
                        with db.session.begin(subtransactions=True):
                            db.session.merge(association)
                        from app.modules.notifications.models import NotificationType

                        if state == CollaborationUserState.REVOKED:
                            self._notify_user(
                                association,
                                self._get_association_for_other_user(user_guid),
                                NotificationType.collab_edit_revoke,
                            )
                        elif state == CollaborationUserState.APPROVED:
                            self._notify_user(
                                association,
                                self._get_association_for_other_user(user_guid),
                                NotificationType.collab_edit_approved,
                            )
                        success = True
        return success

    def initiate_edit_with_other_user(self):
        self.edit_initiator_guid = current_user.guid
        my_assoc = self._get_association_for_user(current_user.guid)
        other_assoc = self._get_association_for_other_user(current_user.guid)
        if (
            my_assoc.read_approval_state == CollaborationUserState.APPROVED
            and other_assoc.read_approval_state == CollaborationUserState.APPROVED
        ):
            if self._is_approval_state_transition_valid(
                my_assoc.read_approval_state, CollaborationUserState.APPROVED
            ):
                my_assoc.edit_approval_state = CollaborationUserState.APPROVED
                with db.session.begin(subtransactions=True):
                    db.session.merge(my_assoc)
            if self._is_approval_state_transition_valid(
                other_assoc.edit_approval_state, CollaborationUserState.PENDING
            ):
                other_assoc.edit_approval_state = CollaborationUserState.PENDING
                with db.session.begin(subtransactions=True):
                    db.session.merge(other_assoc)
        else:
            raise HoustonException(
                log, 'Unable to start edit on unapproved collaboration'
            )

    # This relates to if the user can access the collaboration itself, not the data
    def user_can_access(self, user):
        return user in self.get_users()

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def user_deleted(self, user_association):
        if user_association.read_approval_state == CollaborationUserState.CREATOR:
            # Collaboration creator removal is an odd case, we have to have an initiator so chose an arbitrary member
            new_creator = (
                self.collaboration_user_associations[0]
                if self.collaboration_user_associations[0] != user_association
                else self.collaboration_user_associations[1]
            )
            message = (
                f'Initiator user removed, assigning {new_creator.user_guid} as initiator'
            )
            AuditLog.audit_log_object(log, self, message)
            self.initiator_guid = new_creator.user_guid
            with db.session.begin(subtransactions=True):
                db.session.merge(self)
                db.session.delete(user_association)
        else:
            # If the user is a member and are removed then the collaboration is removed entirely
            self.delete()

    def delete(self):
        AuditLog.delete_object(log, self)
        with db.session.begin(subtransactions=True):
            for assoc in self.collaboration_user_associations:
                db.session.delete(assoc)
            db.session.delete(self)
