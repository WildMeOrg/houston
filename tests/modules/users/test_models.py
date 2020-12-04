# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import pytest

from app.modules.users import models
from tests import utils


def test_User_repr(user_instance):
    assert len(str(user_instance)) > 0


def test_User_auth(user_instance):
    assert user_instance.is_authenticated
    assert not user_instance.is_anonymous


@pytest.mark.parametrize(
    'init_static_roles,is_internal,is_admin,is_staff,is_active',
    [
        (_init_static_roles, _is_internal, _is_admin, _is_staff, _is_active)
        for _init_static_roles in (
            0,
            (
                models.User.StaticRoles.INTERNAL.mask
                | models.User.StaticRoles.ADMIN.mask
                | models.User.StaticRoles.STAFF.mask
                | models.User.StaticRoles.ACTIVE.mask
            ),
        )
        for _is_internal in (False, True)
        for _is_admin in (False, True)
        for _is_staff in (False, True)
        for _is_active in (False, True)
    ],
)
def test_User_static_roles_setting(
    init_static_roles, is_internal, is_admin, is_staff, is_active, user_instance
):
    """
    Static User Roles are saved as bit flags into one ``static_roles``
    integer field. Ideally, it would be better implemented as a custom field,
    and the plugin would be tested separately, but for now this implementation
    is fine, so we test it as it is.
    """
    user_instance.static_roles = init_static_roles

    if is_internal:
        user_instance.set_static_role(user_instance.StaticRoles.INTERNAL)
    else:
        user_instance.unset_static_role(user_instance.StaticRoles.INTERNAL)

    if is_admin:
        user_instance.set_static_role(user_instance.StaticRoles.ADMIN)
    else:
        user_instance.unset_static_role(user_instance.StaticRoles.ADMIN)

    if is_staff:
        user_instance.set_static_role(user_instance.StaticRoles.STAFF)
    else:
        user_instance.unset_static_role(user_instance.StaticRoles.STAFF)

    if is_active:
        user_instance.set_static_role(user_instance.StaticRoles.ACTIVE)
    else:
        user_instance.unset_static_role(user_instance.StaticRoles.ACTIVE)

    assert (
        user_instance.has_static_role(user_instance.StaticRoles.INTERNAL) is is_internal
    )
    assert user_instance.has_static_role(user_instance.StaticRoles.ADMIN) is is_admin
    assert user_instance.has_static_role(user_instance.StaticRoles.STAFF) is is_staff
    assert user_instance.has_static_role(user_instance.StaticRoles.ACTIVE) is is_active
    assert user_instance.is_internal is is_internal
    assert user_instance.is_admin is is_admin
    assert user_instance.is_staff is is_staff
    assert user_instance.is_active is is_active

    if not is_active and not is_staff and not is_admin and not is_internal:
        assert user_instance.static_roles == 0


def test_User_check_owner(user_instance):
    assert user_instance.check_owner(user_instance)

    second_user = utils.generate_user_instance()
    assert not user_instance.check_owner(second_user)


def test_User_find_with_password(
    patch_User_password_scheme, db
):  # pylint: disable=unused-argument
    def create_user(email, password):
        user = models.User(
            email=email,
            password=password,
            full_name='any any any',
        )
        return user

    user1 = create_user('user1@localhost', 'user1password')
    user2 = create_user('user2@localhost', 'user2password')
    with db.session.begin():
        db.session.add(user1)
        db.session.add(user2)

    assert models.User.find('user1@localhost', 'user1password') == user1
    assert models.User.find('user1@localhost', 'wrong-user1password') is None
    assert models.User.find('user2@localhost', 'user1password') is None
    assert models.User.find('user2@localhost', 'user2password') == user2
    assert models.User.find('nouser@localhost', 'userpassword') is None

    with db.session.begin():
        db.session.delete(user1)
        db.session.delete(user2)


def test_User_must_have_password():
    with pytest.raises(ValueError, match='User must have a password'):
        user = models.User(email='user1@localhost', full_name='Lord Lucan')
        print(user)
