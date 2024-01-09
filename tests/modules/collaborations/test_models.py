# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging
from unittest import mock

import pytest

from tests.utils import module_unavailable

log = logging.getLogger(__name__)


@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_collaboration_create_with_members(
    db, collab_user_a, collab_user_b, user_manager_user, request
):  # pylint: disable=unused-argument
    from app.modules.collaborations.models import Collaboration

    members = [collab_user_a, collab_user_b]

    basic_collab = Collaboration(members, collab_user_a)
    request.addfinalizer(basic_collab.delete)

    assert len(basic_collab.get_users()) == 2
    assert basic_collab.initiator_guid == collab_user_a.guid

    for association in basic_collab.collaboration_user_associations:
        assert association.edit_approval_state == 'not_initiated'
        if association.user == collab_user_a:
            assert association.read_approval_state == 'approved'
        else:
            assert association.read_approval_state == 'pending'
    with mock.patch(
        'app.modules.notifications.models.current_user', new=user_manager_user
    ):
        manager_collab = Collaboration(members, user_manager_user)
    request.addfinalizer(manager_collab.delete)

    request.addfinalizer(manager_collab.delete)
    assert manager_collab.initiator_guid is None
    for association in manager_collab.collaboration_user_associations:

        if association.user == user_manager_user:
            assert association.read_approval_state == 'creator'
        else:
            assert association.read_approval_state == 'approved'


@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_collaboration_read_state_changes(db, collab_user_a, collab_user_b, request):
    from app.modules.collaborations.models import Collaboration, CollaborationUserState

    collab = Collaboration([collab_user_a, collab_user_b], collab_user_a)
    with db.session.begin():
        db.session.add(collab)
    request.addfinalizer(collab.delete)

    def set_read_approval_state(*user_guid_states):
        for user_guid, state in user_guid_states:
            collab.set_approval_state_for_user(user_guid, state)
        for association in collab.collaboration_user_associations:
            for user_guid, state in user_guid_states:
                if association.user_guid == user_guid:
                    assert association.read_approval_state == state

    set_read_approval_state(
        (collab_user_a.guid, CollaborationUserState.APPROVED),
        (collab_user_b.guid, CollaborationUserState.DENIED),
    )

    set_read_approval_state(
        (collab_user_a.guid, CollaborationUserState.APPROVED),
        (collab_user_b.guid, CollaborationUserState.DENIED),
    )

    set_read_approval_state(
        (collab_user_a.guid, CollaborationUserState.REVOKED),
        (collab_user_b.guid, CollaborationUserState.DENIED),
    )

    set_read_approval_state(
        (collab_user_a.guid, CollaborationUserState.APPROVED),
        (collab_user_b.guid, CollaborationUserState.APPROVED),
    )
    assert collab_user_a.get_collaboration_associations()[0].has_read()
    assert collab_user_b.get_collaboration_associations()[0].has_read()
    assert (
        collab_user_a.get_collaboration_associations()[0].get_other_user()
        == collab_user_b
    )


@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_collaboration_edit_state_changes(db, collab_user_a, collab_user_b, request):
    from app.modules.collaborations.models import Collaboration, CollaborationUserState

    collab = Collaboration([collab_user_a, collab_user_b], collab_user_a)
    with db.session.begin():
        db.session.add(collab)
    request.addfinalizer(collab.delete)

    json_user_data = collab.get_user_data_as_json()
    assert len(json_user_data.keys()) == 2
    assert str(collab_user_a.guid) in json_user_data.keys()
    assert str(collab_user_b.guid) in json_user_data.keys()

    collab.set_approval_state_for_user(
        collab_user_a.guid, CollaborationUserState.APPROVED
    )
    collab.set_approval_state_for_user(
        collab_user_b.guid, CollaborationUserState.APPROVED
    )
    for association in collab.collaboration_user_associations:
        assert association.read_approval_state == CollaborationUserState.APPROVED
        assert association.edit_approval_state == CollaborationUserState.NOT_INITIATED

    with mock.patch('app.modules.collaborations.models.current_user', new=collab_user_a):
        collab.initiate_edit_with_other_user()

    # TODO test that edit_initiator is set correctly

    for association in collab.collaboration_user_associations:
        if association.user_guid == collab_user_a.guid:
            assert association.edit_approval_state == CollaborationUserState.APPROVED
        if association.user_guid == collab_user_b.guid:
            assert association.edit_approval_state == CollaborationUserState.PENDING
    collab.set_approval_state_for_user(
        collab_user_b.guid, CollaborationUserState.APPROVED, level='edit'
    )

    for association in collab.collaboration_user_associations:
        assert association.edit_approval_state == CollaborationUserState.APPROVED

    # Check that revoking read also revokes edit
    collab.set_approval_state_for_user(collab_user_b.guid, CollaborationUserState.REVOKED)
    for association in collab.collaboration_user_associations:
        if association.user_guid == collab_user_b.guid:
            assert association.edit_approval_state == CollaborationUserState.REVOKED
            assert association.read_approval_state == CollaborationUserState.REVOKED


@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_fail_create_collaboration(collab_user_a, collab_user_b):
    from app.modules.collaborations.models import Collaboration

    def validate_failure(users, initiator):

        with pytest.raises(ValueError):
            collab = Collaboration(members=users, initiator_user=initiator)
            assert collab is None

    # No initiator
    validate_failure([collab_user_a, collab_user_b], None)

    # wrong number members,
    validate_failure([collab_user_a], collab_user_b)

    # wrong number members,
    validate_failure([collab_user_a, collab_user_b, collab_user_b], collab_user_b)

    # member that isn't a user
    validate_failure([collab_user_a, 'random string'], collab_user_b)
