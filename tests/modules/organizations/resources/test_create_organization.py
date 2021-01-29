# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import json
from tests import utils

PATH = '/api/v1/organizations/'


def create_organization(flask_app_client, user, title):
    with flask_app_client.login(user, auth_scopes=('organizations:write',)):
        response = flask_app_client.post(PATH, data=json.dumps({'title': title}))
    return response


def test_create_and_delete_organization(flask_app_client, admin_user, temp_user):
    # pylint: disable=invalid-name
    from app.modules.organizations.models import Organization
    from app.modules.users.models import User

    temp_user.set_static_role(User.StaticRoles.STAFF)
    response = create_organization(
        flask_app_client, temp_user, 'This is a test org, please ignore'
    )
    utils.validate_dict_response(response, 200, {'guid', 'title'})

    organization_guid = response.json['guid']
    read_organization = Organization.query.get(response.json['guid'])
    assert read_organization.title == 'This is a test org, please ignore'
    assert read_organization.owner == temp_user

    # Try reading it back
    with flask_app_client.login(temp_user, auth_scopes=('organizations:read',)):
        response = flask_app_client.get('%s%s' % (PATH, organization_guid))

    utils.validate_dict_response(response, 200, {'guid', 'title'})

    # And deleting it
    with flask_app_client.login(temp_user, auth_scopes=('organizations:write',)):
        response = flask_app_client.delete('%s%s' % (PATH, organization_guid))

    assert response.status_code == 204
    read_organization = Organization.query.get(organization_guid)
    assert read_organization is None

    temp_user.unset_static_role(User.StaticRoles.STAFF)
