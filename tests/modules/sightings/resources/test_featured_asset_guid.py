# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import json
from app.modules.sightings.models import Sighting
from tests.modules.sightings.resources import utils as sighting_utils
from flask import current_app
from tests import utils


def test_featured_asset_guid(db, flask_app_client):

    new_researcher = utils.generate_user_instance(
        email='asset_guid_getter@mail.com', is_researcher=True
    )

    with db.session.begin():
        db.session.add(new_researcher)

    data_in = {
        'encounters': [{}],
        'context': 'test',
        'locationId': 'test',
    }

    response = sighting_utils.create_sighting(
        flask_app_client, new_researcher, data_in=data_in
    )

    sighting_id = response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None

    new_asset_group = utils.generate_asset_group_instance(new_researcher)

    with db.session.begin():
        db.session.add(new_asset_group)
        db.session.add(sighting)

    PATH = '/api/v1/sightings/' + str(sighting.guid) + '/featured_asset_guid'
    SIGHTINGS_READ = 'sightings:read'

    with flask_app_client.login(new_researcher, auth_scopes=(SIGHTINGS_READ,)):
        response = flask_app_client.get(PATH)
    assert response.json['featured_asset_guid'] == 'None'

    new_asset_1 = utils.generate_asset_instance(new_asset_group.guid)
    new_asset_2 = utils.generate_asset_instance(new_asset_group.guid)
    new_asset_3 = utils.generate_asset_instance(new_asset_group.guid)

    with db.session.begin():
        db.session.add(sighting)
        db.session.add(new_asset_group)
        db.session.add(new_asset_1)
        db.session.add(new_asset_2)
        db.session.add(new_asset_3)

    sighting.add_asset(new_asset_1)
    with flask_app_client.login(new_researcher, auth_scopes=(SIGHTINGS_READ,)):
        response = flask_app_client.get(PATH)
    assert response.json['featured_asset_guid'] == str(new_asset_1.guid)

    sighting.add_asset(new_asset_2)

    with flask_app_client.login(new_researcher, auth_scopes=('sightings:write',)):
        response = flask_app_client.post(
            '%s' % PATH,
            content_type='application/json',
            data=json.dumps({'featured_asset_guid': str(new_asset_2.guid)}),
        )

    assert response.json['success'] is True
    with flask_app_client.login(new_researcher, auth_scopes=(SIGHTINGS_READ,)):
        response = flask_app_client.get(PATH)

    assert response.json['featured_asset_guid'] == str(new_asset_2.guid)
    sighting.set_featured_asset_guid(new_asset_3.guid)
    with flask_app_client.login(new_researcher, auth_scopes=(SIGHTINGS_READ,)):
        response = flask_app_client.get(PATH)

    assert response.json['featured_asset_guid'] == str(new_asset_2.guid)

    sighting_utils.delete_sighting(flask_app_client, new_researcher, str(sighting.guid))
    current_app.git_backend.delete_remote_asset_group(new_asset_group)
    new_asset_1.delete()
    new_asset_2.delete()
    new_asset_3.delete()
    with db.session.begin():
        db.session.delete(new_asset_group)

    new_researcher.delete()
