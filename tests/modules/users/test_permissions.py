# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
from unittest.mock import Mock, patch

import pytest
from werkzeug.exceptions import HTTPException

import tests.utils as test_utils
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from tests.utils import module_unavailable


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


@pytest.mark.skipif(
    test_utils.module_unavailable('encounters'), reason='Encounters module disabled'
)
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

    owned_encounter.delete()
    public_encounter.delete()


@pytest.mark.skipif(
    test_utils.module_unavailable('asset_groups'), reason='Asset Groups module disabled'
)
def test_ModuleAccessPermission_anonymous_user(anonymous_user_login):
    # pylint: disable=unused-argument
    from app.modules.asset_groups.models import AssetGroup
    from app.modules.users.models import User

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


@pytest.mark.skipif(
    test_utils.module_unavailable('asset_groups'), reason='Asset Groups module disabled'
)
def test_ModuleAccessPermission_authenticated_user(authenticated_user_login):
    # pylint: disable=unused-argument
    from app.modules.asset_groups.models import AssetGroup
    from app.modules.users.models import User

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


@pytest.mark.skipif(
    test_utils.module_unavailable('asset_groups'), reason='Asset Groups module disabled'
)
def test_ModuleAccessPermission_admin_user(admin_user_login):
    # pylint: disable=unused-argument
    from app.modules.asset_groups.models import AssetGroup
    from app.modules.users.models import User

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


@pytest.mark.skipif(
    test_utils.module_unavailable('asset_groups'), reason='Asset Groups module disabled'
)
def test_ModuleAccessPermission_user_manager_user(user_manager_user_login):
    # pylint: disable=unused-argument
    from app.modules.asset_groups.models import AssetGroup
    from app.modules.users.models import User

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


@pytest.mark.skipif(
    test_utils.module_unavailable('encounters'), reason='Encounters module disabled'
)
def test_ObjectAccessPermission_researcher_user(
    db, researcher_1_login, temp_user, public_encounter, owned_encounter
):
    # pylint: disable=unused-argument
    from app.modules.users.models import User

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

    my_encounter = test_utils.generate_owned_encounter(researcher_1_login)

    with db.session.begin():
        db.session.add(my_encounter)
    validate_can_read_object(my_encounter)
    validate_can_write_object(my_encounter)
    validate_can_delete_object(my_encounter)

    my_encounter.delete()
    owned_encounter.delete()
    public_encounter.delete()


@pytest.mark.skipif(
    test_utils.module_unavailable('encounters'), reason='Encounters module disabled'
)
def test_ObjectAccessPermission_contributor_user(
    db, contributor_1_login, temp_user, public_encounter, owned_encounter
):
    # pylint: disable=unused-argument
    from app.modules.assets.models import Asset
    from app.modules.users.models import User

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
            with patch.object(mock_asset, 'user_can_access', return_value=False):
                # Project access disabled for MVP, the first 3 should be _can_read checks when restored
                validate_cannot_read_object(project1)
                validate_cannot_read_object(owned_encounter)
                validate_cannot_read_object(mock_asset)
                # object that is not a project, encounter or asset
                validate_cannot_read_object(mock_other)

    my_encounter = test_utils.generate_owned_encounter(contributor_1_login)
    with db.session.begin():
        db.session.add(my_encounter)

    validate_can_read_object(my_encounter)
    validate_can_write_object(my_encounter)
    validate_can_delete_object(my_encounter)

    my_encounter.delete()
    owned_encounter.delete()
    public_encounter.delete()


def test_ObjectAccessPermission_user_manager_user(
    db,
    user_manager_user_login,
    temp_user,
):
    # pylint: disable=unused-argument
    from app.modules.users.models import User

    # Can access other users
    validate_can_read_module(User)
    validate_can_write_module(User)

    validate_can_read_object(temp_user)
    validate_can_write_object(temp_user)
    validate_can_delete_object(temp_user)

    obj = Mock()
    obj.is_public = lambda: False

    # user manager user should not be able to access non user stuff
    validate_cannot_read_object(obj)
    validate_cannot_write_object(obj)
    validate_cannot_delete_object(obj)


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_data_manager_and_staff_access(
    db, flask_app_client, researcher_1, data_manager_1, staff_user, request, test_root
):
    import tests.modules.encounters.resources.utils as encounter_utils
    import tests.modules.individuals.resources.utils as individual_utils
    import tests.modules.sightings.resources.utils as sighting_utils

    # testing that staff and data_managers can edit and read these three objects
    uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )
    individual_id = uuids['individual']
    sighting_id = uuids['sighting']

    # any of these methods will throw an error if we don't get a 200 OK response
    ind_patch_data = [
        test_utils.patch_add_op(
            'names',
            {
                'context': 'test_context',
                'value': 'test_value',
            },
        ),
    ]
    individual_utils.patch_individual(
        flask_app_client, data_manager_1, individual_id, ind_patch_data
    )
    indiv_resp = individual_utils.read_individual(
        flask_app_client, staff_user, individual_id
    ).json
    assert indiv_resp['names'][0]['context'] == 'test_context'
    assert indiv_resp['names'][0]['value'] == 'test_value'
    individual_utils.read_individual(flask_app_client, staff_user, individual_id)
    test_dt = '1999-01-01T12:34:56-07:00'
    sight_patch_data = [
        test_utils.patch_replace_op('time', test_dt),
        test_utils.patch_replace_op('timeSpecificity', 'month'),
    ]
    sighting_utils.patch_sighting(
        flask_app_client,
        staff_user,
        sighting_id,
        sight_patch_data,
    )
    sight_resp = sighting_utils.read_sighting(
        flask_app_client, data_manager_1, sighting_id
    ).json
    assert sight_resp['time'] == test_dt
    assert sight_resp['timeSpecificity'] == 'month'

    encounter_id = sight_resp['encounters'][0]['guid']
    patch_data = [test_utils.patch_replace_op('locationId', 'LOCATION_TEST_VALUE')]
    encounter_utils.patch_encounter(
        flask_app_client, encounter_id, data_manager_1, patch_data
    )
    enc_resp = encounter_utils.read_encounter(
        flask_app_client, staff_user, encounter_id
    ).json
    assert enc_resp['locationId'] == 'LOCATION_TEST_VALUE'
