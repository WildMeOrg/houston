# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import json
from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.asset_groups.resources import utils as asset_group_utils
from tests import utils


def test_featured_asset_guid_endpoint(db, flask_app_client, researcher_1):
    from app.modules.sightings.models import Sighting

    data_in = {
        'encounters': [{}],
        'startTime': '2000-01-01T01:01:01Z',
        'locationId': 'test',
    }

    response = sighting_utils.create_sighting(
        flask_app_client, researcher_1, data_in=data_in
    )

    sighting_id = response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None

    new_asset_group = utils.generate_asset_group_instance(researcher_1)

    with db.session.begin():
        db.session.add(new_asset_group)

    PATH = '/api/v1/sightings/' + str(sighting.guid) + '/featured_asset_guid'
    SIGHTINGS_READ = 'sightings:read'

    with flask_app_client.login(researcher_1, auth_scopes=(SIGHTINGS_READ,)):
        response = flask_app_client.get(PATH)

    assert response.json['featured_asset_guid'] is None

    new_asset_1 = utils.generate_asset_instance(new_asset_group.guid)
    new_asset_2 = utils.generate_asset_instance(new_asset_group.guid)
    new_asset_3 = utils.generate_asset_instance(new_asset_group.guid)

    with db.session.begin():
        db.session.add(new_asset_1)
        db.session.add(new_asset_2)
        db.session.add(new_asset_3)

    sighting.add_asset(new_asset_1)
    db.session.refresh(sighting)

    with flask_app_client.login(researcher_1, auth_scopes=(SIGHTINGS_READ,)):
        response = flask_app_client.get(PATH)

    assert str(sighting.get_featured_asset_guid()) == str(new_asset_1.guid)
    assert str(sighting.featured_asset_guid) == str(new_asset_1.guid)
    assert response.json['guid'] == str(sighting.guid)
    assert response.json['featured_asset_guid'] == str(new_asset_1.guid)

    sighting.add_asset(new_asset_2)

    with flask_app_client.login(researcher_1, auth_scopes=('sightings:write',)):
        response = flask_app_client.post(
            '%s' % PATH,
            content_type='application/json',
            data=json.dumps({'featured_asset_guid': str(new_asset_2.guid)}),
        )

    assert response.json['success'] is True
    with flask_app_client.login(researcher_1, auth_scopes=(SIGHTINGS_READ,)):
        response = flask_app_client.get(PATH)

    assert response.json['featured_asset_guid'] == str(new_asset_2.guid)
    sighting.set_featured_asset_guid(new_asset_3.guid)
    with flask_app_client.login(researcher_1, auth_scopes=(SIGHTINGS_READ,)):
        response = flask_app_client.get(PATH)

    assert response.json['featured_asset_guid'] == str(new_asset_2.guid)

    # new_asset_group.delete_remote()
    # new_asset_group.delete()
    # sighting_utils.delete_sighting(flask_app_client, researcher_1, str(sighting.guid))

    from app.modules.asset_groups.tasks import delete_remote

    sighting_utils.delete_sighting(flask_app_client, researcher_1, str(sighting.guid))
    delete_remote(str(new_asset_group.guid))
    asset_group_utils.delete_asset_group(
        flask_app_client, researcher_1, new_asset_group.guid
    )


def test_patch_featured_asset_guid(db, flask_app_client, researcher_1):
    from app.modules.sightings.models import Sighting

    data_in = {
        'encounters': [{}],
        'startTime': '2000-01-01T01:01:01Z',
        'locationId': 'test',
    }

    response = sighting_utils.create_sighting(
        flask_app_client, researcher_1, data_in=data_in
    )

    sighting_id = response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None

    new_asset_group = utils.generate_asset_group_instance(researcher_1)

    with db.session.begin():
        db.session.add(new_asset_group)

    new_asset_1 = utils.generate_asset_instance(new_asset_group.guid)
    new_asset_2 = utils.generate_asset_instance(new_asset_group.guid)

    with db.session.begin():
        db.session.add(new_asset_group)
        db.session.add(new_asset_1)
        db.session.add(new_asset_2)

    sighting.add_asset(new_asset_1)

    assert new_asset_1.guid == sighting.get_featured_asset_guid()

    sighting.add_asset_no_context(new_asset_2)
    db.session.refresh(sighting)

    patch_op = [
        utils.patch_replace_op('featuredAssetGuid', '%s' % new_asset_2.guid),
    ]

    sighting_utils.patch_sighting(
        flask_app_client, researcher_1, '%s' % sighting.guid, patch_op
    )

    assert new_asset_2.guid == sighting.get_featured_asset_guid()

    from app.modules.asset_groups.tasks import delete_remote

    sighting_utils.delete_sighting(flask_app_client, researcher_1, str(sighting.guid))
    delete_remote(str(new_asset_group.guid))
    asset_group_utils.delete_asset_group(
        flask_app_client, researcher_1, new_asset_group.guid
    )
