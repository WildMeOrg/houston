# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests import utils

from flask import current_app

from tests.modules.sightings.resources import utils as sighting_utils


PATH = '/api/v1/sightings/'


def no_test_asset_addition(db, flask_app_client):
    # pylint: disable=invalid-name
    from app.modules.sightings.models import Sighting

    new_researcher = utils.generate_user_instance(
        email='reseracher47@nowhere.com', is_researcher=True
    )
    new_sighting = Sighting()
    new_asset_group = utils.generate_asset_group_instance(new_researcher)
    new_asset = utils.generate_asset_instance(new_asset_group.guid)

    with db.session.begin():
        db.session.add(new_researcher)
        db.session.add(new_sighting)
        db.session.add(new_asset_group)
        db.session.add(new_asset)

    add_asset = [
        utils.patch_test_op(new_researcher.password_secret),
        utils.patch_add_op('assetId', '%s' % new_asset.guid),
    ]
    sighting_utils.patch_sighting(
        flask_app_client, '%s' % new_sighting.guid, new_researcher, add_asset
    )
    assert len(new_sighting.assets) == 1
    # removed submission delete as it was going haywire
    current_app.agm.delete_remote_asset_group(new_asset_group)
    new_asset_group.delete()
    new_researcher.delete()
    new_asset.delete()
    new_sighting.delete()


def add_file_asset_to_sighting(
    flask_app_client, user, sighting, transaction_id, filename, content
):
    # for efficiency, just write the files into the place that tus would upload them to
    import os

    uploads_dir = flask_app_client.application.config['UPLOADS_DATABASE_PATH']
    dir_path = os.path.join(uploads_dir, '-'.join(['trans', transaction_id]))
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    with open(os.path.join(dir_path, filename), 'a') as file:
        file.write(content)
        file.close()

    add_asset = [
        utils.patch_add_op('newAssetGroup', transaction_id),
    ]
    sighting_utils.patch_sighting(flask_app_client, user, '%s' % sighting.guid, add_asset)

    assert os.path.exists(dir_path) is False


def test_asset_file_addition(db, flask_app_client, staff_user):
    # pylint: disable=invalid-name
    from app.modules.sightings.models import Sighting

    new_researcher = utils.generate_user_instance(
        email='asset_adder@user.com', is_researcher=True
    )

    with db.session.begin():
        db.session.add(new_researcher)

    data_in = {
        'context': 'test',
        'locationId': 'test',
        'encounters': [{}],
    }
    response = sighting_utils.create_sighting(
        flask_app_client, new_researcher, expected_status_code=200, data_in=data_in
    )
    sighting_id = response.json['result']['id']
    new_sighting = Sighting.query.get(sighting_id)

    try:
        add_file_asset_to_sighting(
            flask_app_client,
            new_researcher,
            new_sighting,
            'new_stuff',
            'new_file.csv',
            '1,2,3,4,5',
        )
        assert len(new_sighting.assets) == 1
        add_file_asset_to_sighting(
            flask_app_client,
            new_researcher,
            new_sighting,
            'more_stuff',
            'next_file.csv',
            '5,4,3,2,1',
        )
        assert len(new_sighting.assets) == 2

    finally:
        sighting_utils.delete_sighting(flask_app_client, staff_user, sighting_id)
        new_researcher.delete()
        # assets are only cleaned up once the submissions are cleaned up
        for asset_group in new_researcher.asset_groups:
            current_app.agm.delete_remote_asset_group(asset_group)
            asset_group.delete()
