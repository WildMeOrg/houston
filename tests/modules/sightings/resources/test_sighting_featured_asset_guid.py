# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.asset_groups.resources import utils as asset_group_utils
from tests.extensions.tus import utils as tus_utils
from tests import utils
import pytest
import uuid

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
    from app.modules.sightings.models import Sighting

    # Create an asset group with a bunch of data to play around with
    transaction_id, test_filename = asset_group_utils.create_bulk_tus_transaction(
        test_root
    )
    request.addfinalizer(lambda: tus_utils.cleanup_tus_dir(transaction_id))

    data = asset_group_utils.get_bulk_creation_data_one_sighting(
        transaction_id, test_filename
    )
    ag_create_response = asset_group_utils.create_asset_group(
        flask_app_client, researcher_1, data.get()
    )
    asset_group_uuid = ag_create_response.json['guid']
    request.addfinalizer(
        lambda: asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, asset_group_uuid
        )
    )
    asset_group_sighting_guid = ag_create_response.json['asset_group_sightings'][0][
        'guid'
    ]

    # Commit it and get the sighting to know what we created
    commit_response = asset_group_utils.commit_asset_group_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid
    )
    sighting_guid = commit_response.json['guid']
    sighting = Sighting.query.get(sighting_guid)
    request.addfinalizer(lambda: sighting.delete_cascade())

    featured_asset = [
        asset
        for asset in ag_create_response.json['assets']
        if asset['guid'] == str(sighting.featured_asset_guid)
    ]
    assert len(featured_asset) == 1

    image_response = sighting_utils.read_sighting_path(
        flask_app_client, researcher_1, f'{sighting_guid}/featured_image'
    )
    assert image_response.content_type == 'image/jpeg'
    asset_group_utils.validate_file_data(
        image_response.data, featured_asset[0]['filename']
    )

    # make fluke the featured asset, It may have been anyway but if the code fails this will catch it
    fluke_assets = [
        asset
        for asset in ag_create_response.json['assets']
        if asset['filename'] == 'fluke.jpg'
    ]
    assert len(fluke_assets) == 1
    sighting.set_featured_asset_guid(uuid.UUID(fluke_assets[0]['guid']))

    # Reread the path, should now be the other asset
    image_response = sighting_utils.read_sighting_path(
        flask_app_client, researcher_1, f'{sighting_guid}/featured_image'
    )
    assert image_response.content_type == 'image/jpeg'
    asset_group_utils.validate_file_data(image_response.data, 'fluke.jpg')
