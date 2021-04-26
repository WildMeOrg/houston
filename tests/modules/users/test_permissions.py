# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
from mock import Mock, patch
import pytest

from werkzeug.exceptions import HTTPException

from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation


# helpers to make object and module reading and writing testing more intuitive
class NotARealClass(object):
    # fake class for the module tests as the code checks against None
    pass


def validate_can_read_object(obj):
    with permissions.ObjectAccessPermission(obj=obj, action=AccessOperation.READ):
        pass


def validate_cannot_read_object(obj):
    with pytest.raises(HTTPException):
        with permissions.ObjectAccessPermission(obj=obj, action=AccessOperation.READ):
            pass


def validate_can_write_object(obj):
    with permissions.ObjectAccessPermission(obj=obj, action=AccessOperation.WRITE):
        pass


def validate_cannot_write_object(obj):
    with pytest.raises(HTTPException):
        with permissions.ObjectAccessPermission(obj=obj, action=AccessOperation.WRITE):
            pass


def validate_can_delete_object(obj):
    with permissions.ObjectAccessPermission(obj=obj, action=AccessOperation.DELETE):
        pass


def validate_cannot_delete_object(obj):
    with pytest.raises(HTTPException):
        with permissions.ObjectAccessPermission(obj=obj, action=AccessOperation.DELETE):
            pass


def validate_can_read_module(module):
    with permissions.ModuleAccessPermission(module=module, action=AccessOperation.READ):
        pass


def validate_cannot_read_module(module):
    with pytest.raises(HTTPException):
        with permissions.ModuleAccessPermission(
            module=module, action=AccessOperation.READ
        ):
            pass


def validate_can_write_module(module):
    with permissions.ModuleAccessPermission(module=module, action=AccessOperation.WRITE):
        pass


def validate_cannot_write_module(module):
    with pytest.raises(HTTPException):
        with permissions.ModuleAccessPermission(
            module=module, action=AccessOperation.WRITE
        ):
            pass


def validate_can_delete_module(module):
    with permissions.ModuleAccessPermission(module=module, action=AccessOperation.DELETE):
        pass


def validate_cannot_delete_module(module):
    with pytest.raises(HTTPException):
        with permissions.ModuleAccessPermission(
            module=module, action=AccessOperation.DELETE
        ):
            pass


def test_DenyAbortMixin():
    with pytest.raises(HTTPException):
        permissions.rules.DenyAbortMixin().deny()


def test_ActiveUserRoleRule_anonymous(anonymous_user_login):
    # pylint: disable=unused-argument
    assert permissions.rules.ActiveUserRoleRule().check() is False


def test_ActiveUserRoleRule_authenticated_user(authenticated_user_login):
    authenticated_user_login.is_active = True
    assert permissions.rules.ActiveUserRoleRule().check() is True
    authenticated_user_login.is_active = False
    assert permissions.rules.ActiveUserRoleRule().check() is False


def test_PasswordRequiredRule(authenticated_user_login):
    authenticated_user_login.password = 'correct_password'
    assert (
        permissions.rules.PasswordRequiredRule(password='correct_password').check()
        is True
    )
    assert (
        permissions.rules.PasswordRequiredRule(password='wrong_password').check() is False
    )


def test_AdminRoleRule_authenticated_user(authenticated_user_login):
    authenticated_user_login.is_admin = True
    assert permissions.rules.AdminRoleRule().check() is True
    authenticated_user_login.is_admin = False
    assert permissions.rules.AdminRoleRule().check() is False


def test_PartialPermissionDeniedRule():
    with pytest.raises(RuntimeError):
        permissions.rules.PartialPermissionDeniedRule().check()


def test_PasswordRequiredPermissionMixin():
    mixin = permissions.PasswordRequiredPermissionMixin(password_required=False)
    with pytest.raises(AttributeError):
        mixin.rule()


def test_RolePermission():
    with permissions.RolePermission():
        pass
    with pytest.raises(RuntimeError):
        with permissions.RolePermission(partial=True):
            pass


def test_ActiveUserRolePermission_anonymous_user(anonymous_user_login):
    # pylint: disable=unused-argument
    with pytest.raises(HTTPException):
        with permissions.ActiveUserRolePermission():
            pass


def test_ActiveUserRolePermission_authenticated_user(authenticated_user_login):
    authenticated_user_login.is_active = True
    with permissions.ActiveUserRolePermission():
        pass
    authenticated_user_login.is_active = False
    with pytest.raises(HTTPException):
        with permissions.ActiveUserRolePermission():
            pass


def test_AdminRolePermission_anonymous_user(anonymous_user_login):
    # pylint: disable=unused-argument
    with pytest.raises(HTTPException):
        with permissions.AdminRolePermission():
            pass


def test_AdminRolePermission_authenticated_user(authenticated_user_login):
    authenticated_user_login.is_admin = True
    with permissions.AdminRolePermission():
        pass
    authenticated_user_login.is_admin = False
    with pytest.raises(HTTPException):
        with permissions.AdminRolePermission():
            pass


def test_AdminRolePermission_anonymous_user_with_password(anonymous_user_login):
    # pylint: disable=unused-argument
    with pytest.raises(HTTPException):
        with permissions.AdminRolePermission(
            password_required=True, password='any_password'
        ):
            pass


def test_AdminRolePermission_authenticated_user_with_password_is_admin(
    authenticated_user_login,
):
    authenticated_user_login.password = 'correct_password'
    authenticated_user_login.is_admin = True
    with permissions.AdminRolePermission(
        password_required=True, password='correct_password'
    ):
        pass
    with pytest.raises(HTTPException):
        with permissions.AdminRolePermission(
            password_required=True, password='wrong_password'
        ):
            pass


def test_AdminRolePermission_authenticated_user_with_password_not_admin(
    authenticated_user_login,
):
    authenticated_user_login.password = 'correct_password'
    authenticated_user_login.is_admin = False
    with pytest.raises(HTTPException):
        with permissions.AdminRolePermission(
            password_required=True, password='correct_password'
        ):
            pass
    with pytest.raises(HTTPException):
        with permissions.AdminRolePermission(
            password_required=True, password='wrong_password'
        ):
            pass


def test_ObjectAccessPermission_anonymous_user(anonymous_user_login):
    # pylint: disable=unused-argument
    obj = Mock()
    obj.is_public = lambda: True

    # anon user should only be able to read public data
    validate_can_read_object(obj)
    validate_cannot_write_object(obj)
    validate_cannot_delete_object(obj)

    obj.is_public = lambda: False
    validate_cannot_read_object(obj)
    validate_cannot_write_object(obj)
    validate_cannot_delete_object(obj)


def test_ObjectAccessPermission_authenticated_user(authenticated_user_login):
    # pylint: disable=unused-argument
    obj = Mock()
    obj.is_public = lambda: True

    # regular user should have same permissions as anon user for objects they don't own
    validate_can_read_object(obj)
    validate_cannot_write_object(obj)
    validate_cannot_delete_object(obj)

    obj.is_public = lambda: False
    validate_cannot_read_object(obj)
    validate_cannot_write_object(obj)
    validate_cannot_delete_object(obj)

    # but be able to do what they like if they own the object.
    # Here be dragons. Everything in python is changable including the address of methods in objects.
    # store the previous one for restoration and then get owns_object to do what we want for testing
    try:
        prev_owns_object = authenticated_user_login.owns_object
        authenticated_user_login.owns_object = lambda obj: True
        validate_can_read_object(obj)
        validate_can_write_object(obj)
        validate_can_delete_object(obj)
    finally:
        # reset back to the real one and check that it works
        authenticated_user_login.owns_object = prev_owns_object

    validate_cannot_read_object(obj)
    validate_cannot_write_object(obj)
    validate_cannot_delete_object(obj)


def test_ObjectAccessPermission_admin_user(
    admin_user_login, temp_user, public_encounter, owned_encounter
):
    # pylint: disable=unused-argument

    obj = Mock()
    obj.is_public = lambda: False

    # Admin user should not be able to do what they like
    validate_cannot_read_object(obj)
    validate_cannot_write_object(obj)
    validate_cannot_delete_object(obj)

    obj.is_public = lambda: True
    validate_can_read_object(obj)
    validate_cannot_write_object(obj)
    validate_cannot_delete_object(obj)

    validate_can_read_object(temp_user)
    validate_can_write_object(temp_user)
    validate_can_delete_object(temp_user)

    validate_can_read_object(public_encounter)
    validate_cannot_write_object(public_encounter)
    validate_cannot_delete_object(public_encounter)

    validate_cannot_read_object(owned_encounter)
    validate_cannot_write_object(owned_encounter)
    validate_cannot_delete_object(owned_encounter)


def test_ModuleAccessPermission_anonymous_user(anonymous_user_login):
    # pylint: disable=unused-argument
    from app.modules.users.models import User
    from app.modules.asset_groups.models import AssetGroup

    # anon user cannot do anything with most classes
    validate_cannot_read_module(NotARealClass)
    validate_cannot_write_module(NotARealClass)
    validate_cannot_delete_module(NotARealClass)

    # but can write a user (sign up) or an asset_group
    validate_cannot_read_module(User)
    validate_can_write_module(User)
    validate_cannot_delete_module(User)

    validate_cannot_read_module(AssetGroup)
    validate_can_write_module(AssetGroup)
    validate_cannot_delete_module(AssetGroup)


def test_ModuleAccessPermission_authenticated_user(authenticated_user_login):
    # pylint: disable=unused-argument
    from app.modules.users.models import User
    from app.modules.asset_groups.models import AssetGroup

    # regular users also shouldn't be able to access most classes
    validate_cannot_read_module(NotARealClass)
    validate_cannot_write_module(NotARealClass)
    validate_cannot_delete_module(NotARealClass)

    # but can they write (create) users & (upload) asset_groups,
    validate_cannot_read_module(User)
    validate_can_write_module(User)
    validate_cannot_delete_module(User)

    validate_cannot_read_module(AssetGroup)
    validate_can_write_module(AssetGroup)
    validate_cannot_delete_module(AssetGroup)


def test_ModuleAccessPermission_admin_user(admin_user_login):
    # pylint: disable=unused-argument
    from app.modules.users.models import User
    from app.modules.asset_groups.models import AssetGroup

    # Admin users cannot do what they like
    validate_cannot_read_module(NotARealClass)
    validate_cannot_write_module(NotARealClass)
    validate_cannot_delete_module(NotARealClass)

    # Has virtually no access to users other than creation
    validate_cannot_read_module(User)
    validate_can_write_module(User)
    validate_cannot_delete_module(User)

    # Admin users can list AssetGroups
    validate_can_read_module(AssetGroup)
    validate_can_write_module(AssetGroup)
    validate_cannot_delete_module(AssetGroup)


def test_ModuleAccessPermission_user_manager_user(user_manager_user_login):
    # pylint: disable=unused-argument
    from app.modules.users.models import User
    from app.modules.asset_groups.models import AssetGroup

    # user Admins not especially priviliged
    validate_cannot_read_module(NotARealClass)
    validate_cannot_write_module(NotARealClass)
    validate_cannot_delete_module(NotARealClass)

    # But can read all users
    validate_can_read_module(User)
    validate_can_write_module(User)
    validate_cannot_delete_module(User)

    # But not Data, other than create assetGroups like everyone else
    validate_cannot_read_module(AssetGroup)
    validate_can_write_module(AssetGroup)
    validate_cannot_delete_module(AssetGroup)


def test_ObjectAccessPermission_researcher_user(
    db, researcher_1_login, temp_user, public_encounter, owned_encounter
):
    # pylint: disable=unused-argument
    from app.modules.users.models import User
    from app.modules.encounters.models import Encounter

    # Can't access other users
    validate_cannot_read_module(User)
    validate_can_write_module(User)
    validate_cannot_delete_module(User)

    validate_cannot_read_object(temp_user)
    validate_cannot_write_object(temp_user)
    validate_cannot_delete_object(temp_user)

    obj = Mock()
    obj.is_public = lambda: False

    # Researcher user should not be able to access everything
    validate_cannot_read_object(obj)
    validate_cannot_write_object(obj)
    validate_cannot_delete_object(obj)

    obj.is_public = lambda: True
    validate_can_read_object(obj)
    validate_cannot_write_object(obj)
    validate_cannot_delete_object(obj)

    validate_can_read_object(public_encounter)
    validate_cannot_write_object(public_encounter)
    validate_cannot_delete_object(public_encounter)

    validate_can_read_object(owned_encounter)
    validate_cannot_write_object(owned_encounter)
    validate_cannot_delete_object(owned_encounter)

    my_encounter = Encounter(owner=researcher_1_login)

    with db.session.begin():
        db.session.add(my_encounter)
    validate_can_read_object(my_encounter)
    validate_can_write_object(my_encounter)
    validate_can_delete_object(my_encounter)


def test_ObjectAccessPermission_contributor_user(
    db, contributor_1_login, temp_user, public_encounter, owned_encounter
):
    # pylint: disable=unused-argument
    from app.modules.assets.models import Asset
    from app.modules.users.models import User
    from app.modules.encounters.models import Encounter

    # Can't access other users
    validate_cannot_read_module(User)
    validate_can_write_module(User)
    validate_cannot_delete_module(User)

    validate_cannot_read_object(temp_user)
    validate_cannot_write_object(temp_user)
    validate_cannot_delete_object(temp_user)

    obj = Mock()
    obj.is_public = lambda: False

    # contributor user should not be able to access everything
    validate_cannot_read_object(obj)
    validate_cannot_write_object(obj)
    validate_cannot_delete_object(obj)

    obj.is_public = lambda: True
    validate_can_read_object(obj)
    validate_cannot_write_object(obj)
    validate_cannot_delete_object(obj)

    validate_can_read_object(public_encounter)
    validate_cannot_write_object(public_encounter)
    validate_cannot_delete_object(public_encounter)

    validate_cannot_read_object(owned_encounter)
    validate_cannot_write_object(owned_encounter)
    validate_cannot_delete_object(owned_encounter)

    # project, encounter, asset permitted via project
    project1 = Mock(is_public=lambda: False, get_encounters=lambda: [])
    project2 = Mock(is_public=lambda: False)
    project2.get_encounters.return_value = [Mock(get_assets=lambda: []), owned_encounter]
    mock_asset = Mock(__class__=Asset, is_public=lambda: False)
    project3 = Mock(is_public=lambda: False)
    project3.get_encounters.return_value = [Mock(get_assets=lambda: [mock_asset])]
    # object that is not a project, encounter or asset
    mock_other = Mock(is_public=lambda: False)
    projects = [project1, project2, project3]
    with patch.object(contributor_1_login, 'owns_object', return_value=False):
        with patch.object(contributor_1_login, 'get_projects', return_value=projects):
            # Project access disabled for MVP, the first 3 should be _can_read checks when restored
            validate_cannot_read_object(project1)
            validate_cannot_read_object(owned_encounter)
            validate_cannot_read_object(mock_asset)
            # object that is not a project, encounter or asset
            validate_cannot_read_object(mock_other)

    my_encounter = Encounter(owner=contributor_1_login)
    with db.session.begin():
        db.session.add(my_encounter)

    validate_can_read_object(my_encounter)
    validate_can_write_object(my_encounter)
    validate_can_delete_object(my_encounter)
