# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import sqlalchemy

from tests import utils
from tests.modules.sightings.resources import utils as sighting_utils


def test_asset_addition(db, flask_app_client, staff_user):
    # pylint: disable=invalid-name
    from app.modules.sightings.models import Sighting

    try:
        new_researcher = utils.generate_user_instance(
            email='adder_of_assets@mail.com', is_researcher=True
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
        new_asset_group = utils.generate_asset_group_instance(new_researcher)

        with db.session.begin():
            db.session.add(new_asset_group)

        new_asset_1 = utils.generate_asset_instance(new_asset_group.guid)
        new_asset_2 = utils.generate_asset_instance(new_asset_group.guid)
        new_asset_3 = utils.generate_asset_instance(new_asset_group.guid)

        with db.session.begin():
            db.session.add(new_sighting)
            db.session.add(new_asset_group)
            db.session.add(new_asset_1)
            db.session.add(new_asset_2)
            db.session.add(new_asset_3)

        # lets try a list internally first
        assets = [new_asset_1, new_asset_2]
        new_sighting.add_assets(assets)

        assert len(new_sighting.assets) == 2

        add_asset = [
            utils.patch_add_op('assetId', '%s' % new_asset_3.guid),
        ]

        sighting_utils.patch_sighting(
            flask_app_client, new_researcher, '%s' % new_sighting.guid, add_asset
        )

        assert len(new_sighting.assets) == 3

    finally:
        # staff can do this, no need to revisit encounter based ownership here
        sighting_utils.delete_sighting(
            flask_app_client, staff_user, str(new_sighting.guid)
        )
        new_asset_group.delete_remote()
        new_asset_1.delete()
        new_asset_2.delete()
        new_asset_3.delete()
        try:
            new_asset_group.delete()
        except sqlalchemy.exc.InvalidRequestError:  # already deleted
            pass
        new_researcher.delete()

        with db.session.begin():
            db.session.delete(new_asset_group)


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
            asset_group.delete_remote()
            asset_group.delete()
