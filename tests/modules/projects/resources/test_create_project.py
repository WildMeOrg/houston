# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import json


def test_create_and_delete_project(flask_app_client, regular_user):
    # pylint: disable=invalid-name

    from app.modules.projects.models import Project

    with flask_app_client.login(regular_user, auth_scopes=('projects:write',)):
        response = flask_app_client.post(
            '/api/v1/projects/',
            data=json.dumps(
                {
                    'title': 'This is a test project, please ignore',
                }
            ),
        )

    assert response.status_code == 200
    assert response.content_type == 'application/json'
    assert isinstance(response.json, dict)
    assert set(response.json.keys()) >= {
        'guid',
        'title',
    }

    project_guid = response.json['guid']
    read_project = Project.query.get(response.json['guid'])
    assert read_project.title == 'This is a test project, please ignore'

    # Try reading it back
    with flask_app_client.login(regular_user, auth_scopes=('projects:read',)):
        response = flask_app_client.get('/api/v1/projects/%s' % project_guid)

    assert response.status_code == 200
    assert response.content_type == 'application/json'
    assert isinstance(response.json, dict)
    assert set(response.json.keys()) >= {
        'guid',
        'title',
    }

    # And deleting it
    with flask_app_client.login(regular_user, auth_scopes=('projects:write',)):
        response = flask_app_client.delete('/api/v1/projects/%s' % project_guid)

    # For now projects cannot be deleted
    assert response.status_code == 403
    read_project = Project.query.get(project_guid)
    assert read_project is not None
