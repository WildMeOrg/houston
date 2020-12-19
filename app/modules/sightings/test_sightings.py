# -*- coding: utf-8 -*-
import json


def sighting_create_and_destroy(flask_app_client, regular_user):

    from app.modules.projects.models import Sighting

    with flask_app_client.login(regular_user, auth_scopes=('sightings:write',)):
        response = flask_app_client.post(
            '/api/v1/sightings/',
            data=json.dumps(
                {
                    'title': 'Testing generated.',
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

    sighting_guid = response.json['guid']
    read_sighting = Sighting.query.get(response.json['guid'])
    assert read_sighting.title == 'Testing generated.'

    with flask_app_client.login(regular_user, auth_scopes=('sightings:read',)):
        response = flask_app_client.get('/api/v1/sightings/%s' % sighting_guid)

    assert response.status_code == 200
    assert response.content_type == 'application/json'
    assert isinstance(response.json, dict)
    assert set(response.json.keys()) >= {
        'guid',
        'title',
    }

    with flask_app_client.login(regular_user, auth_scopes=('sightings:write',)):
        response = flask_app_client.delete('/api/v1/sightings/%s' % sighting_guid)

    assert response.status_code == 204
    read_sighting = Sighting.query.get(sighting_guid)
    assert read_sighting is None
