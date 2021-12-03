# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests import utils
from tests.modules.sightings.resources import utils as sighting_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_asset_addition(
    db, flask_app_client, staff_user, researcher_1, request, test_root
):
    # pylint: disable=invalid-name
    from app.modules.sightings.models import Sighting

    try:
        uuids = sighting_utils.create_sighting(
            flask_app_client, researcher_1, request, test_root
        )
        sighting_id = uuids['sighting']
        new_sighting = Sighting.query.get(sighting_id)
        new_asset_group = utils.generate_asset_group_instance(researcher_1)

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

        assert len(new_sighting.sighting_assets) == 3

        add_asset = [
            utils.patch_add_op('assetId', '%s' % new_asset_3.guid),
        ]

        sighting_utils.patch_sighting(
            flask_app_client, researcher_1, '%s' % new_sighting.guid, add_asset
        )

        assert len(new_sighting.sighting_assets) == 4

    except AssertionError as ex:
        import tests.modules.asset_groups.resources.utils as asset_group_utils

        asset_group_utils.delete_asset_group(
            flask_app_client, staff_user, uuids['asset_group']
        )
        raise ex


@pytest.mark.skipif(
    module_unavailable('sightings', 'asset_group'), reason='Sightings module disabled'
)
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


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_asset_file_addition(
    db, flask_app_client, staff_user, researcher_1, request, test_root
):
    # pylint: disable=invalid-name
    from app.modules.sightings.models import Sighting

    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root
    )
    sighting_id = uuids['sighting']
    new_sighting = Sighting.query.get(sighting_id)

    add_file_asset_to_sighting(
        flask_app_client,
        researcher_1,
        new_sighting,
        'new_stuff',
        'new_file.csv',
        '1,2,3,4,5',
    )
    assert len(new_sighting.sighting_assets) == 2
    add_file_asset_to_sighting(
        flask_app_client,
        researcher_1,
        new_sighting,
        'more_stuff',
        'next_file.csv',
        '5,4,3,2,1',
    )
    assert len(new_sighting.sighting_assets) == 3
