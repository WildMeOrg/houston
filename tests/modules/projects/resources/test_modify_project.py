# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils
from tests.modules.projects.resources import utils as proj_utils


def test_modify_project(db, flask_app_client, admin_user, temp_user, regular_user):
    # pylint: disable=invalid-name
    # from app.modules.projects.models import Project
    # from app.modules.encounters.models import Encounter

    response = proj_utils.create_project(
        flask_app_client, temp_user, 'This is a test project, please ignore'
    )

    utils.validate_dict_response(response, 200, {'guid', 'title'})

    project_guid = response.json['guid']
    data = [
        utils.patch_test_op(admin_user.password_secret),
        utils.patch_add_op(
            '%s' % regular_user.guid,
            'User',
        ),
    ]
    response = proj_utils.patch_project(flask_app_client, project_guid, admin_user, data)
    utils.validate_dict_response(response, 200, {'guid', 'title'})

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
    with flask_app_client.login(admin_user, auth_scopes=('projects:write',)):
        response = flask_app_client.delete('/api/v1/projects/%s' % project_guid)

    assert response.status_code == 204


def test_project_permission(db, flask_app_client, regular_user, admin_user, temp_user):

    response = proj_utils.create_project(
        flask_app_client, temp_user, 'This is a test project, please ignore'
    )

    utils.validate_dict_response(response, 200, {'guid', 'title'})

    project_guid = response.json['guid']
    # user that is a member cannot update project

    response = proj_utils.patch_project(
        flask_app_client,
        project_guid,
        temp_user,
        {'title': 'This is a modified test project, please ignore'},
    )
    utils.validate_dict_response(response, 403, {'status', 'message'})

    # only admin can do that
    response = proj_utils.patch_project(
        flask_app_client,
        project_guid,
        admin_user,
        {'title': 'This is a modified test project, please ignore'},
    )
    utils.validate_dict_response(response, 200, {'guid', 'title'})

    # User also cannot delete the project
    with flask_app_client.login(temp_user, auth_scopes=('projects:write',)):
        response = flask_app_client.delete('/api/v1/projects/%s' % project_guid)

    utils.validate_dict_response(response, 403, {'status', 'message'})

    # delete it
    with flask_app_client.login(admin_user, auth_scopes=('projects:write',)):
        response = flask_app_client.delete('/api/v1/projects/%s' % project_guid)

    assert response.status_code == 204
