# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils
from tests.modules.projects.resources import utils as proj_utils


def test_create_and_delete_project(flask_app_client, admin_user, temp_user):
    # pylint: disable=invalid-name
    from app.modules.projects.models import Project

    response = proj_utils.create_project(
        flask_app_client, temp_user, 'This is a test project, please ignore'
    )

    utils.validate_dict_response(
        response,
        200,
        {
            'guid',
            'title',
        },
    )

    project_guid = response.json['guid']
    read_project = Project.query.get(response.json['guid'])
    assert read_project.title == 'This is a test project, please ignore'

    # Try reading it back
    with flask_app_client.login(temp_user, auth_scopes=('projects:read',)):
        response = flask_app_client.get('/api/v1/projects/%s' % project_guid)

    utils.validate_dict_response(response, 200, {'guid', 'title'})

    # And deleting it, which requires admin
    with flask_app_client.login(admin_user, auth_scopes=('projects:write',)):
        response = flask_app_client.delete('/api/v1/projects/%s' % project_guid)

    assert response.status_code == 204
    read_project = Project.query.get(project_guid)
    assert read_project is None


def test_project_permission(db, flask_app_client, regular_user, admin_user, temp_user):

    response = proj_utils.create_project(
        flask_app_client, temp_user, 'This is a test project, please ignore'
    )

    utils.validate_dict_response(response, 200, {'guid', 'title'})

    project_guid = response.json['guid']

    # user that created project can read it back but not the list
    with flask_app_client.login(temp_user, auth_scopes=('projects:read',)):
        list_response = flask_app_client.get('/api/v1/projects/')
        proj_response = flask_app_client.get('/api/v1/projects/%s' % project_guid)
    utils.validate_dict_response(list_response, 403, {'status', 'message'})
    utils.validate_dict_response(proj_response, 200, {'guid', 'title'})

    # admin user should be able to read all projects
    with flask_app_client.login(admin_user, auth_scopes=('projects:read',)):
        list_response = flask_app_client.get('/api/v1/projects/')
        proj_response = flask_app_client.get('/api/v1/projects/%s' % project_guid)
    assert list_response.status_code == 200
    assert list_response.content_type == 'application/json'
    assert isinstance(list_response.json, list)
    assert len(list_response.json) == 1
    assert list_response.json[0]['guid'] == project_guid

    assert proj_response.status_code == 200

    # but a different user cannot read either
    with flask_app_client.login(regular_user, auth_scopes=('projects:read',)):
        list_response = flask_app_client.get('/api/v1/projects/')
        proj_response = flask_app_client.get('/api/v1/projects/%s' % project_guid)
    utils.validate_dict_response(list_response, 403, {'status', 'message'})
    utils.validate_dict_response(proj_response, 403, {'status', 'message'})

    # delete it
    with flask_app_client.login(admin_user, auth_scopes=('projects:write',)):
        response = flask_app_client.delete('/api/v1/projects/%s' % project_guid)

    assert response.status_code == 204
