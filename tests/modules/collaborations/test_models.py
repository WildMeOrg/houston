# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

# import sqlalchemy

import logging

from app.modules.collaborations.models import Collaboration
from app.modules.collaborations.models import CollaborationUserState

log = logging.getLogger(__name__)


def test_collaboration_create_with_members(
    db, collab_user_a, collab_user_b
):  # pylint: disable=unused-argument
    # collab create will fail if the users are non persisted
    with db.session.begin():
        db.session.add(collab_user_a)
        db.session.add(collab_user_b)

    guids = [collab_user_a.get_id(), collab_user_b.get_id()]

    simple_collab = Collaboration(title='Simple Collab', user_guids=guids)

    assert len(simple_collab.get_users()) == 2

    specific_collab = Collaboration(
        title='Specific Collab',
        user_guids=[collab_user_a.guid, collab_user_b.guid],
        approval_states=['approved', 'approved'],
        initiator_states=[True, False],
    )

    assert len(specific_collab.get_users()) == 2

    for association in specific_collab.collaboration_user_associations:
        assert association.read_approval_state == 'approved'

        if association.user.guid == collab_user_a.guid:
            assert association.initiator is True
        else:
            assert association.initiator is False


def test_collaboration_read_state_changes(db, collab_user_a, collab_user_b):
    collab = Collaboration(
        title='Collab for state change',
        user_guids=[collab_user_a.guid, collab_user_b.guid],
        initiator_states=[True, False],
    )
    with db.session.begin():
        db.session.add(collab)

    for association in collab.collaboration_user_associations:
        if association.user_guid == collab_user_a.guid:
            assert (
                association.read_approval_state == CollaborationUserState.APPROVED
            )  # flagged initiator, automatic approval
        elif association.user_guid == collab_user_b.guid:
            assert association.read_approval_state == CollaborationUserState.PENDING

        assert association.edit_approval_state == CollaborationUserState.NOT_INITIATED

    def set_read_approval_state(*user_guid_states):
        for user_guid, state in user_guid_states:
            collab.set_read_approval_state_for_user(user_guid, state)
        for association in collab.collaboration_user_associations:
            for user_guid, state in user_guid_states:
                if association.user_guid == user_guid:
                    assert association.read_approval_state == state

    set_read_approval_state(
        (collab_user_a.guid, CollaborationUserState.APPROVED),
        (collab_user_b.guid, CollaborationUserState.DECLINED),
    )

    assert collab.get_read_state() == CollaborationUserState.DECLINED

    set_read_approval_state(
        (collab_user_a.guid, CollaborationUserState.PENDING),
        (collab_user_b.guid, CollaborationUserState.DECLINED),
    )

    assert collab.get_read_state() == CollaborationUserState.DECLINED

    set_read_approval_state(
        (collab_user_a.guid, CollaborationUserState.DECLINED),
        (collab_user_b.guid, CollaborationUserState.PENDING),
    )

    assert collab.get_read_state() == CollaborationUserState.DECLINED

    set_read_approval_state(
        (collab_user_a.guid, CollaborationUserState.APPROVED),
        (collab_user_b.guid, CollaborationUserState.APPROVED),
    )

    assert collab.get_read_state() == CollaborationUserState.APPROVED


def test_collaboration_edit_state_changes(db, collab_user_a, collab_user_b):

    collab = Collaboration(
        title='Collab for state change',
        user_guids=[collab_user_a.guid, collab_user_b.guid],
        initiator_states=[True, False],
    )

    for association in collab.collaboration_user_associations:
        assert association.edit_approval_state == CollaborationUserState.NOT_INITIATED

    assert collab.get_edit_state() == CollaborationUserState.NOT_INITIATED

    collab.set_edit_approval_state_for_user(
        collab_user_a.guid, CollaborationUserState.APPROVED
    )

    for association in collab.collaboration_user_associations:
        if association.user_guid == collab_user_a.guid:
            assert association.read_approval_state == CollaborationUserState.APPROVED
        if association.user_guid == collab_user_b.guid:
            assert association.read_approval_state == CollaborationUserState.PENDING

    assert collab.get_edit_state() == CollaborationUserState.PENDING

    collab.set_edit_approval_state_for_user(
        collab_user_b.guid, CollaborationUserState.APPROVED
    )

    assert collab.get_edit_state() == CollaborationUserState.APPROVED
