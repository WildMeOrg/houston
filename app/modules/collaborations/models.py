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
        'denied',
        'approved',
        'pending',
        'not_initiated',
        'revoked',
    ]
    DENIED = ALLOWED_STATES[0]
    APPROVED = ALLOWED_STATES[1]
    PENDING = ALLOWED_STATES[2]
    NOT_INITIATED = ALLOWED_STATES[3]
    REVOKED = ALLOWED_STATES[4]


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
        self.collaboration.user_deleted()

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
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True
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

        self.initiator_guid = None if manager_created else initiator_user.guid
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

            from app.modules.notifications.models import NotificationType

            if notify_users:
                for user in members:
                    user_assoc = self._get_association_for_user(user.guid)
                    self._notify_user(
                        current_user,
                        user_assoc.user,
                        NotificationType.collab_manager_create,
                    )

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
            ]
            assert len(other_user_guids) == 1

            assoc = self._get_association_for_user(other_user_guids[0])
        return assoc

    def get_users(self):
        return [assoc.user for assoc in self.collaboration_user_associations]

    def user_guids(self):
        return [assoc.user_guid for assoc in self.collaboration_user_associations]

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
                        other_user_assoc.user,
                        collab_user_assoc.user,
                        NotificationType.collab_request,
                    )

                if (
                    collab_user_assoc.edit_approval_state
                    == CollaborationUserState.PENDING
                ):
                    self._notify_user(
                        other_user_assoc.user,
                        collab_user_assoc.user,
                        NotificationType.collab_edit_request,
                    )

    def _notify_user(self, sending_user, receiving_user, notification_type, manager=None):
        from app.modules.notifications.models import (
            Notification,
            NotificationBuilder,
            NotificationType,
        )

        builder = NotificationBuilder(sending_user)
        builder.set_collaboration(self, manager)
        notif = Notification.create(notification_type, receiving_user, builder)

        if notification_type is NotificationType.collab_request:
            self.init_req_notification_guid = notif.guid
        elif notification_type is NotificationType.collab_edit_request:
            self.edit_req_notification_guid = notif.guid

        # in these states, every notification has been read/resolved
        fully_resolved_notification_states = {
            NotificationType.collab_edit_approved,
            NotificationType.collab_edit_revoke,
            NotificationType.collab_revoke,
            NotificationType.collab_manager_revoke,
            NotificationType.collab_denied,
        }

        # set necessary notification.is_resolved fields
        if notification_type == NotificationType.collab_approved:
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
                CollaborationUserState.APPROVED,
                CollaborationUserState.PENDING,
            ]
        elif old_state == CollaborationUserState.PENDING:
            ret_val = new_state in [
                CollaborationUserState.APPROVED,
                CollaborationUserState.DENIED,
            ]
        elif old_state == CollaborationUserState.APPROVED:
            ret_val = new_state == CollaborationUserState.REVOKED
        elif old_state == CollaborationUserState.DENIED:
            ret_val = new_state == CollaborationUserState.APPROVED
        elif old_state == CollaborationUserState.REVOKED:
            ret_val = new_state == CollaborationUserState.APPROVED

        # Permit resetting to same state in all cases rather than handling separately for each
        if not ret_val:
            ret_val = old_state == new_state

        return ret_val

    def set_read_approval_state_for_user(self, user_guid, state):
        from app.modules.notifications.models import NotificationType

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

                        if state == CollaborationUserState.REVOKED:
                            self._notify_user(
                                association.user,
                                self._get_association_for_other_user(user_guid).user,
                                NotificationType.collab_revoke,
                            )
                        elif state == CollaborationUserState.APPROVED:
                            self._notify_user(
                                association.user,
                                self._get_association_for_other_user(user_guid).user,
                                NotificationType.collab_approved,
                            )
                        elif state == CollaborationUserState.DENIED:
                            self._notify_user(
                                association.user,
                                self._get_association_for_other_user(user_guid).user,
                                NotificationType.collab_denied,
                            )
                        with db.session.begin(subtransactions=True):
                            db.session.merge(association)
                        success = True

            # user managers can set the states too, but only valid transitions
            if not success and current_user.is_user_manager:
                assocs = self.collaboration_user_associations
                if self._is_approval_state_transition_valid(
                    assocs[0].read_approval_state, state
                ) and self._is_approval_state_transition_valid(
                    assocs[1].read_approval_state, state
                ):
                    for assoc in assocs:
                        assoc.read_approval_state = state

                        if state == CollaborationUserState.REVOKED:
                            # If the user manager revokes view and edit was previously allowed, they automatically
                            # revoke edit too
                            if (
                                assoc.edit_approval_state
                                == CollaborationUserState.APPROVED
                            ):
                                assoc.edit_approval_state = state

                            self._notify_user(
                                current_user,
                                assoc.user,
                                NotificationType.collab_manager_revoke,
                            )
                        elif state == CollaborationUserState.APPROVED:
                            self._notify_user(
                                current_user,
                                assoc.user,
                                NotificationType.collab_approved,
                            )
                        elif state == CollaborationUserState.DENIED:
                            self._notify_user(
                                current_user,
                                assoc.user,
                                NotificationType.collab_denied,
                            )
                        with db.session.begin(subtransactions=True):
                            db.session.merge(assoc)
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
                                association.user,
                                self._get_association_for_other_user(user_guid).user,
                                NotificationType.collab_edit_revoke,
                            )
                        elif state == CollaborationUserState.APPROVED:
                            self._notify_user(
                                association.user,
                                self._get_association_for_other_user(user_guid).user,
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

    def user_deleted(self):
        self.delete()

    def delete(self):
        AuditLog.delete_object(log, self)
        with db.session.begin(subtransactions=True):
            for assoc in self.collaboration_user_associations:
                db.session.delete(assoc)
            db.session.delete(self)
