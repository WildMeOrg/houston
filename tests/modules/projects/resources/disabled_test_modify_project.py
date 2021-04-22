# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils
from tests.modules.projects.resources import utils as proj_utils


def test_modify_project(db, flask_app_client, admin_user, researcher_1, researcher_2):

    # pylint: disable=invalid-name
    from app.modules.projects.models import Project
    from app.modules.encounters.models import Encounter

    response = proj_utils.create_project(
        flask_app_client, researcher_1, 'This is a test project, please ignore'
    )
    project_guid = response.json['guid']

    proj = Project.query.get(project_guid)
    assert len(proj.get_members()) == 1

    data = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_add_op('user', '%s' % researcher_2.guid),
    ]
    proj_utils.patch_project(flask_app_client, project_guid, researcher_1, data)
    assert len(proj.get_members()) == 2

    data = [
        utils.patch_test_op(admin_user.password_secret),
        utils.patch_remove_op('user', '%s' % researcher_2.guid),
    ]
    proj_utils.patch_project(flask_app_client, project_guid, admin_user, data, 403)
    assert len(proj.get_members()) == 2

    data = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_remove_op('user', '%s' % researcher_2.guid),
    ]
    proj_utils.patch_project(flask_app_client, project_guid, researcher_1, data)
    assert len(proj.get_members()) == 1

    # Create encounters for testing with
    new_encounter_1 = Encounter()
    new_encounter_2 = Encounter()
    new_encounter_3 = Encounter()
    with db.session.begin():
        db.session.add(new_encounter_1)
        db.session.add(new_encounter_2)
        db.session.add(new_encounter_3)

    # add them to the project
    add_encounters = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_add_op('encounter', '%s' % new_encounter_1.guid),
        utils.patch_add_op('encounter', '%s' % new_encounter_2.guid),
        utils.patch_add_op('encounter', '%s' % new_encounter_3.guid),
    ]
    proj_utils.patch_project(flask_app_client, project_guid, researcher_1, add_encounters)
    assert len(proj.get_encounters()) == 3

    # remove some of them
    remove_encounters = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_remove_op('encounter', '%s' % new_encounter_1.guid),
        utils.patch_remove_op('encounter', '%s' % new_encounter_2.guid),
    ]
    proj_utils.patch_project(
        flask_app_client, project_guid, researcher_1, remove_encounters
    )
    assert len(proj.get_encounters()) == 1

    proj_utils.delete_project(flask_app_client, researcher_1, project_guid)


def test_invalid_encounters(
    db,
    flask_app_client,
    admin_user,
    researcher_1,
    researcher_2,
    test_empty_asset_group_uuid,
):
    # pylint: disable=invalid-name
    from app.modules.projects.models import Project
    from app.modules.encounters.models import Encounter

    response = proj_utils.create_project(
        flask_app_client, researcher_1, 'This is a test project, please ignore'
    )
    project_guid = response.json['guid']

    proj = Project.query.get(project_guid)

    # Create encounters for testing with
    new_encounter_1 = Encounter()
    new_encounter_2 = Encounter()
    new_encounter_3 = Encounter()
    with db.session.begin():
        db.session.add(new_encounter_1)
        db.session.add(new_encounter_2)
        db.session.add(new_encounter_3)

    # add some of them to the project
    add_encounters = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_add_op('encounter', '%s' % new_encounter_1.guid),
        utils.patch_add_op('encounter', '%s' % new_encounter_2.guid),
    ]
    proj_utils.patch_project(flask_app_client, project_guid, researcher_1, add_encounters)
    assert len(proj.get_encounters()) == 2

    # Try adding a garbage guid
    add_invalid = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_add_op('encounter', '%s' % test_empty_asset_group_uuid),
    ]
    proj_utils.patch_project(
        flask_app_client, project_guid, researcher_1, add_invalid, 409
    )
    assert len(proj.get_encounters()) == 2

    # remove one not in the project
    remove_not_present = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_remove_op('encounter', '%s' % new_encounter_3.guid),
    ]
    # Expect this to "succeed" as the UUID is not part of the project as was requested
    proj_utils.patch_project(
        flask_app_client, project_guid, researcher_1, remove_not_present
    )
    assert len(proj.get_encounters()) == 2

    # remove garbage guid
    remove_invalid = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_remove_op('encounter', '%s' % test_empty_asset_group_uuid),
    ]
    proj_utils.patch_project(flask_app_client, project_guid, researcher_1, remove_invalid)
    assert len(proj.get_encounters()) == 2
    proj_utils.delete_project(flask_app_client, researcher_1, project_guid)


def test_owner_permission(flask_app_client, researcher_1, researcher_2):
    response = proj_utils.create_project(
        flask_app_client, researcher_1, 'This is a test project, please ignore'
    )
    project_guid = response.json['guid']

    # another user cannot update the title
    data = [
        utils.patch_test_op(researcher_2.password_secret),
        utils.patch_add_op('title', 'Invalid update'),
    ]
    proj_utils.patch_project(flask_app_client, project_guid, researcher_2, data, 403)

    # Owner can do that
    data = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_add_op('title', 'An owner modified test project, please ignore'),
    ]
    response = proj_utils.patch_project(
        flask_app_client, project_guid, researcher_1, data
    )
    assert response.json['title'] == 'An owner modified test project, please ignore'

    # Encounter addition and removal not tested for owner as it's already tested in test_modify_project

    # add researcher 2 user to the project
    data = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_add_op('user', '%s' % researcher_2.guid),
    ]
    proj_utils.patch_project(flask_app_client, project_guid, researcher_1, data)

    # make them the owner
    data = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_add_op('owner', '%s' % researcher_2.guid),
    ]
    proj_utils.patch_project(flask_app_client, project_guid, researcher_1, data)

    # try to remove a user as researcher1, no longer owner, should fail
    data = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_remove_op('user', '%s' % researcher_2.guid),
    ]
    proj_utils.patch_project(flask_app_client, project_guid, researcher_1, data, 409)

    # TODO: This returns a 200, due to the default of True in PatchJSONParameters:perform_patch

    # response = proj_utils.patch_project(
    #     flask_app_client,
    #     project_guid,
    #     temp_user,
    #     {'title': 'This is an owner modified test project, please ignore'},
    # )
    # utils.validate_dict_response(response, 200, {'guid', 'title'})
    # # It does at least fail to do anything
    # assert response.json['title'] == 'This is an admin modified test project, please ignore'


def test_member_permission(db, flask_app_client, researcher_1, researcher_2):
    from app.modules.projects.models import Project
    from app.modules.encounters.models import Encounter

    response = proj_utils.create_project(
        flask_app_client, researcher_1, 'This is a test project, please ignore'
    )
    project_guid = response.json['guid']

    # add researcher 2 user to the project
    data = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_add_op('user', '%s' % researcher_2.guid),
    ]
    proj_utils.patch_project(flask_app_client, project_guid, researcher_1, data)

    proj = Project.query.get(project_guid)
    assert len(proj.get_encounters()) == 0

    # Create encounters for testing with
    new_encounter_1 = Encounter()
    new_encounter_2 = Encounter()
    new_encounter_3 = Encounter()
    with db.session.begin():
        db.session.add(new_encounter_1)
        db.session.add(new_encounter_2)
        db.session.add(new_encounter_3)

    # add them to the project
    add_encounters = [
        utils.patch_test_op(researcher_2.password_secret),
        utils.patch_add_op('encounter', '%s' % new_encounter_1.guid),
        utils.patch_add_op('encounter', '%s' % new_encounter_2.guid),
        utils.patch_add_op('encounter', '%s' % new_encounter_3.guid),
    ]
    proj_utils.patch_project(flask_app_client, project_guid, researcher_2, add_encounters)
    assert len(proj.get_encounters()) == 3

    # remove some of them
    remove_encounters = [
        utils.patch_test_op(researcher_2.password_secret),
        utils.patch_remove_op('encounter', '%s' % new_encounter_1.guid),
        utils.patch_remove_op('encounter', '%s' % new_encounter_2.guid),
    ]
    proj_utils.patch_project(
        flask_app_client, project_guid, researcher_2, remove_encounters
    )
    assert len(proj.get_encounters()) == 1

    # Member should not be able to remove project
    proj_utils.delete_project(flask_app_client, researcher_2, project_guid, 403)
    # but owner should
    proj_utils.delete_project(flask_app_client, researcher_1, project_guid)


def test_non_member_permission(db, flask_app_client, researcher_1, researcher_2):
    from app.modules.projects.models import Project
    from app.modules.encounters.models import Encounter

    response = proj_utils.create_project(
        flask_app_client, researcher_1, 'This is a test project, please ignore'
    )
    project_guid = response.json['guid']

    # Create encounters for testing with
    new_encounter_1 = Encounter()
    new_encounter_2 = Encounter()
    new_encounter_3 = Encounter()
    with db.session.begin():
        db.session.add(new_encounter_1)
        db.session.add(new_encounter_2)
        db.session.add(new_encounter_3)

    # try to add them to the project
    add_as_researcher_2 = [
        utils.patch_test_op(researcher_2.password_secret),
        utils.patch_add_op('encounter', '%s' % new_encounter_1.guid),
        utils.patch_add_op('encounter', '%s' % new_encounter_2.guid),
        utils.patch_add_op('encounter', '%s' % new_encounter_3.guid),
    ]
    proj_utils.patch_project(
        flask_app_client, project_guid, researcher_2, add_as_researcher_2, 403
    )
    proj = Project.query.get(project_guid)
    assert len(proj.get_encounters()) == 0

    # add them as owner
    add_as_researcher_1 = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_add_op('encounter', '%s' % new_encounter_1.guid),
        utils.patch_add_op('encounter', '%s' % new_encounter_2.guid),
        utils.patch_add_op('encounter', '%s' % new_encounter_3.guid),
    ]
    proj_utils.patch_project(
        flask_app_client, project_guid, researcher_1, add_as_researcher_1
    )
    proj = Project.query.get(project_guid)
    assert len(proj.get_encounters()) == 3

    # try to remove some of them
    remove_encounters = [
        utils.patch_test_op(researcher_2.password_secret),
        utils.patch_remove_op('encounter', '%s' % new_encounter_1.guid),
        utils.patch_remove_op('encounter', '%s' % new_encounter_2.guid),
    ]
    proj_utils.patch_project(
        flask_app_client, project_guid, researcher_2, remove_encounters, 403
    )
    assert len(proj.get_encounters()) == 3

    # non Member should not be able to remove project
    proj_utils.delete_project(flask_app_client, researcher_2, project_guid, 403)
    # but owner should
    proj_utils.delete_project(flask_app_client, researcher_1, project_guid)
