# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import pytest


def test_linked_account(researcher_1):
    from app.modules.users.models import User

    with pytest.raises(ValueError):
        researcher_1.link_account('foo', 123)
    data = {'id': 123, 'other_key': 456}
    researcher_1.link_account('foo', data)
    assert len(researcher_1.linked_accounts) == 1

    found = User.find_by_linked_account('foo', 999)
    assert not found
    found = User.find_by_linked_account('foo', 999, 'something')
    assert not found
    found = User.find_by_linked_account('foo', 123)
    assert found == researcher_1
    found = User.find_by_linked_account('foo', 456, 'other_key')
    assert found == researcher_1
