# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.asset_groups.resources import utils as asset_group_utils
from tests import utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
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

    path = f'{str(sighting.guid)}/featured_asset_guid'
    response = sighting_utils.read_sighting_path(flask_app_client, researcher_1, path)
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

    response = sighting_utils.read_sighting_path(flask_app_client, researcher_1, path)

    assert str(sighting.get_featured_asset_guid()) == str(new_asset_1.guid)
    assert str(sighting.featured_asset_guid) == str(new_asset_1.guid)
    assert response.json['guid'] == str(sighting.guid)
    assert response.json['featured_asset_guid'] == str(new_asset_1.guid)

    # The Asset was created by a hanging sighting, not part of an asset group, this will fail as that's not
    # how assets should be created
    sighting_utils.read_sighting_path(
        flask_app_client, researcher_1, f'{sighting.guid}/featured_image', 400
    )
    sighting.add_asset(new_asset_2)

    asset_guid_data = {'featured_asset_guid': str(new_asset_2.guid)}
    response = sighting_utils.write_sighting_path(
        flask_app_client, researcher_1, path, asset_guid_data
    )

    assert response.json['success'] is True
    response = sighting_utils.read_sighting_path(flask_app_client, researcher_1, path)

    assert response.json['featured_asset_guid'] == str(new_asset_2.guid)
    sighting.set_featured_asset_guid(new_asset_3.guid)
    response = sighting_utils.read_sighting_path(flask_app_client, researcher_1, path)

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


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_patch_featured_asset_guid_on_sighting(db, flask_app_client, researcher_1):
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


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_featured_sighting_read(db, flask_app_client, researcher_1, test_root, request):

    asset_group, sightings = asset_group_utils.create_asset_group_and_sighting(
        flask_app_client, researcher_1, request, test_root
    )

    assert len(sightings) > 0
    sighting = sightings[0]
    assert len(sighting.encounters) > 0

    image_response = sighting_utils.read_sighting_path(
        flask_app_client, researcher_1, f'{sighting.guid}/featured_image'
    )
    assert image_response.content_type == 'image/jpeg'

    featured_asset = [
        asset
        for asset in asset_group.assets
        if asset.guid == sighting.featured_asset_guid
    ]
    assert len(featured_asset) == 1
    asset_group_utils.validate_file_data(image_response.data, featured_asset[0].filename)

    # make fluke the featured asset, It may have been anyway but if the code fails this will catch it
    fluke_assets = [
        asset for asset in asset_group.assets if asset.filename == 'fluke.jpg'
    ]
    assert len(fluke_assets) == 1
    sighting.set_featured_asset_guid(fluke_assets[0].guid)

    # Reread the path, should now be the other asset
    image_response = sighting_utils.read_sighting_path(
        flask_app_client, researcher_1, f'{sighting.guid}/featured_image'
    )
    assert image_response.content_type == 'image/jpeg'
    asset_group_utils.validate_file_data(image_response.data, 'fluke.jpg')
