# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

# import sqlalchemy

import logging

from app.modules.users.models import User
from app.modules.collaborations.models import Collaboration

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
