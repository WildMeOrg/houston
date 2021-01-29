# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils
from tests.modules.projects.resources import utils as proj_utils


def test_modify_project(db, flask_app_client, admin_user, researcher_user, regular_user):
    # pylint: disable=invalid-name
    from app.modules.projects.models import Project

    # from app.modules.encounters.models import Encounter

    response = proj_utils.create_project(
        flask_app_client, researcher_user, 'This is a test project, please ignore'
    )

    utils.validate_dict_response(response, 200, {'guid', 'title'})
    assert response.json['title'] == 'This is a test project, please ignore'

    project_guid = response.json['guid']

    proj = Project.query.get(project_guid)
    assert len(proj.get_members()) == 1

    data = [
        utils.patch_test_op(researcher_user.password_secret),
        utils.patch_add_op('%s' % regular_user.guid, 'user'),
    ]
    response = proj_utils.patch_project(
        flask_app_client, project_guid, researcher_user, data
    )
    utils.validate_dict_response(response, 200, {'guid', 'title'})
    assert len(proj.get_members()) == 2

    data = [
        utils.patch_test_op(admin_user.password_secret),
        utils.patch_remove_op('user', '%s' % regular_user.guid),
    ]
    response = proj_utils.patch_project(flask_app_client, project_guid, admin_user, data)

    utils.validate_dict_response(response, 200, {'guid', 'title'})
    assert len(proj.get_members()) == 1

    # This is not the way to add an encounter but I think we need Jons EDM work to have a decent way to know
    # what the correct way is
    # @todo when jon finished EDM sync work
    # new_encounter = Encounter()
    # with db.session.begin:
    #     db.session.add(new_encounter)
    #
    # data = [
    #     utils.patch_test_op(admin_user.password_secret),
    #     utils.patch_add_op('%s' % new_encounter.guid, 'Encounter',),
    # ]
    # response = proj_utils.patch_project(flask_app_client, project_guid, admin_user, data)
    # utils.validate_dict_response(response, 200, {'guid', 'title'})

    # delete the project
    with flask_app_client.login(admin_user, auth_scopes=('projects:delete',)):
        response = flask_app_client.delete('/api/v1/projects/%s' % project_guid)

    assert response.status_code == 204


def test_project_permission(flask_app_client, regular_user, admin_user, researcher_user):
    response = proj_utils.create_project(
        flask_app_client, researcher_user, 'This is a test project, please ignore'
    )

    utils.validate_dict_response(response, 200, {'guid', 'title'})

    project_guid = response.json['guid']

    # another user cannot update the title
    data = [
        utils.patch_test_op(regular_user.password_secret),
        utils.patch_add_op('Invalid update', 'title'),
    ]
    response = proj_utils.patch_project(
        flask_app_client,
        project_guid,
        regular_user,
        data,
    )
    utils.validate_dict_response(response, 403, {'status', 'message'})

    # Owner can do that
    data = [
        utils.patch_test_op(researcher_user.password_secret),
        utils.patch_add_op(
            'This is an owner modified test project, please ignore', 'title'
        ),
    ]
    response = proj_utils.patch_project(
        flask_app_client,
        project_guid,
        researcher_user,
        data,
    )
    utils.validate_dict_response(response, 200, {'guid', 'title'})
    assert (
        response.json['title'] == 'This is an owner modified test project, please ignore'
    )

    # as can admin
    data = [
        utils.patch_test_op(admin_user.password_secret),
        utils.patch_add_op(
            'This is an admin modified test project, please ignore', 'title'
        ),
    ]
    response = proj_utils.patch_project(
        flask_app_client,
        project_guid,
        admin_user,
        data,
    )
    utils.validate_dict_response(response, 200, {'guid', 'title'})
    assert (
        response.json['title'] == 'This is an admin modified test project, please ignore'
    )

    # add regular user to the project
    data = [
        utils.patch_test_op(researcher_user.password_secret),
        utils.patch_add_op('%s' % regular_user.guid, 'user'),
    ]
    response = proj_utils.patch_project(
        flask_app_client, project_guid, researcher_user, data
    )
    utils.validate_dict_response(response, 200, {'guid', 'title'})

    # make them the owner
    data = [
        utils.patch_test_op(researcher_user.password_secret),
        utils.patch_add_op('%s' % regular_user.guid, 'owner'),
    ]
    response = proj_utils.patch_project(
        flask_app_client, project_guid, researcher_user, data
    )
    utils.validate_dict_response(response, 200, {'guid', 'title'})

    # try to delete as temp_user, no longer owner, should fail
    data = [
        utils.patch_test_op(researcher_user.password_secret),
        utils.patch_remove_op('user', '%s' % regular_user.guid),
    ]
    response = proj_utils.patch_project(
        flask_app_client, project_guid, researcher_user, data
    )
    utils.validate_dict_response(response, 409, {'status', 'message'})

    # # @todo, This returns a 200, due to the default of True in PatchJSONParameters:perform_patch

    # response = proj_utils.patch_project(
    #     flask_app_client,
    #     project_guid,
    #     temp_user,
    #     {'title': 'This is an owner modified test project, please ignore'},
    # )
    # utils.validate_dict_response(response, 200, {'guid', 'title'})
    # # It does at least fail to do anything
    # assert response.json['title'] == 'This is an admin modified test project, please ignore'

    # tempUser also cannot delete the project
    with flask_app_client.login(researcher_user, auth_scopes=('projects:delete',)):
        response = flask_app_client.delete('/api/v1/projects/%s' % project_guid)

    utils.validate_dict_response(response, 403, {'status', 'message'})

    # regular_user (owner) can delete it
    with flask_app_client.login(regular_user, auth_scopes=('projects:delete',)):
        response = flask_app_client.delete('/api/v1/projects/%s' % project_guid)

    assert response.status_code == 204
