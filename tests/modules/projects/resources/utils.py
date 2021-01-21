# -*- coding: utf-8 -*-
"""
Project resources utils
-------------
"""
import json

PATH = '/api/v1/projects/'


def create_project(flask_app_client, user, title):
    with flask_app_client.login(user, auth_scopes=('projects:write',)):
        response = flask_app_client.post(PATH, data=json.dumps({'title': title}))
    return response


def patch_project(flask_app_client, project_guid, user, data):
    with flask_app_client.login(user, auth_scopes=('projects:write',)):
        response = flask_app_client.patch(
            '%s%s' % (PATH, project_guid),
            content_type='application/json',
            data=json.dumps(data),
        )
    return response
