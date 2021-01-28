# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

# import sqlalchemy

import logging

from app.modules.users.models import User
from app.modules.collaborations.models import Collaboration
from app.modules.collaborations.models import CollaborationUserState

log = logging.getLogger(__name__)


def test_collaboration_create_with_members(db):  # pylint: disable=unused-argument

    user_a = User(
        email='trout@foo.bar',
        password='trout',
        full_name='Mr Trouty',
    )

    user_b = User(
        email='salmon@foo.bar',
        password='salmon',
        full_name='Mr Salmon',
    )

    # collab create will fail if the users are non persisted
    with db.session.begin():
        db.session.add(user_a)
        db.session.add(user_b)

    guids = [user_a.get_id(), user_b.get_id()]

    simple_collab = Collaboration(title='Simple Collab', user_guids=guids)

    assert len(simple_collab.get_users()) == 2

    specific_collab = Collaboration(
        title='Specific Collab',
        user_guids=[user_a.guid, user_b.guid],
        approval_states=['approved', 'approved'],
        is_initiator=[True, False],
    )

    assert len(specific_collab.get_users()) == 2

    for association in specific_collab.collaboration_user_associations:
        assert association.read_approval_state == 'approved'

        if association.user.guid == user_a.guid:
            assert association.initiator is True
        else:
            assert association.initiator is False


def test_collaboration_read_state_changes():
    user_a = User(
        email='trout@foo.bar',
        password='trout',
        full_name='Mr Trouty',
    )

    user_b = User(
        email='salmon@foo.bar',
        password='salmon',
        full_name='Mr Salmon',
    )

    collab = Collaboration(
        title='Collab for state change',
        user_guids=[user_a.guid, user_b.guid],
        is_initiator=[True, False],
    )

    from app.modules.collaborations.models import CollaborationUserState

    for association in collab.collaboration_user_associations:
        if association.user_guid == user_a.guid:
            assert (
                association.read_approval_state == CollaborationUserState.APPROVED
            )  # flagged initiator, automatic approval
        elif association.user_guid == user_b.guid:
            assert association.read_approval_state == CollaborationUserState.PENDING

        assert association.edit_approval_state == CollaborationUserState.NOT_INITIATED

    collab.set_read_approval_state_for_user(user_a.guid, CollaborationUserState.APPROVED)
    collab.set_read_approval_state_for_user(user_b.guid, CollaborationUserState.DECLINED)

    assert collab.get_read_state() == CollaborationUserState.DECLINED

    for association in collab.collaboration_user_associations:
        if association.user_guid == user_a.guid:
            assert association.read_approval_state == CollaborationUserState.APPROVED
        if association.user_guid == user_b.guid:
            assert association.read_approval_state == CollaborationUserState.DECLINED


def test_collaboration_edit_state_changes():
    user_a = User(
        email='trout@foo.bar',
        password='trout',
        full_name='Mr Trouty',
    )

    user_b = User(
        email='salmon@foo.bar',
        password='salmon',
        full_name='Mr Salmon',
    )

    collab = Collaboration(
        title='Collab for state change',
        user_guids=[user_a.guid, user_b.guid],
        is_initiator=[True, False],
    )

    for association in collab.collaboration_user_associations:
        assert association.edit_approval_state == CollaborationUserState.NOT_INITIATED

    assert collab.get_edit_state() == CollaborationUserState.NOT_INITIATED

    collab.set_edit_approval_state_for_user(user_a.guid, CollaborationUserState.APPROVED)

    for association in collab.collaboration_user_associations:
        if association.user_guid == user_a.guid:
            assert association.read_approval_state == CollaborationUserState.APPROVED
        if association.user_guid == user_b.guid:
            assert association.read_approval_state == CollaborationUserState.PENDING

    assert collab.get_edit_state() == CollaborationUserState.PENDING

    collab.set_edit_approval_state_for_user(user_b.guid, CollaborationUserState.APPROVED)

    assert collab.get_edit_state() == CollaborationUserState.APPROVED
