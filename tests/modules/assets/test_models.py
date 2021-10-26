# -*- coding: utf-8 -*-
import pathlib
import shutil
from unittest import mock
import uuid

from PIL import Image
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups', 'sightings'), reason='AssetGroups module disabled'
)
def set_up_assets(flask_app, db, test_root, admin_user, request):
    from app.modules.annotations.models import Annotation
    from app.modules.asset_groups.models import AssetGroup
    from app.modules.asset_groups.metadata import AssetGroupMetadata
    from app.modules.sightings.models import Sighting, SightingAssets, SightingStage

    from tests.modules.asset_groups.resources.utils import AssetGroupCreationData

    def cleanup(func):
        def inner():
            try:
                func()
            except:  # noqa
                pass

        request.addfinalizer(inner)

    # Add jpg files to tus transaction dir
    transaction_id = str(uuid.uuid4())
    tus_dir = pathlib.Path(flask_app.config['UPLOADS_DATABASE_PATH'])
    trans_dir = tus_dir / f'trans-{transaction_id}'
    trans_dir.mkdir(parents=True)
    jpgs = list(test_root.glob('*.jpg'))
    for jpg in jpgs:
        with (trans_dir / jpg.name).open('wb') as f:
            with jpg.open('rb') as g:
                f.write(g.read())

    cleanup(lambda: shutil.rmtree(trans_dir))

    # Create asset group from metadata
    data = AssetGroupCreationData(transaction_id)
    data.set_sighting_field(-1, 'assetReferences', [jpg.name for jpg in jpgs])
    metadata = AssetGroupMetadata(data.get())
    with mock.patch('app.modules.asset_groups.metadata.current_user', new=admin_user):
        metadata.process_request()
    assert metadata.owner == admin_user
    asset_group = AssetGroup.create_from_metadata(metadata)
    cleanup(lambda: db.session.delete(asset_group))

    # Create annotation and sighting and sighting assets for the first asset
    annotation = Annotation(
        asset_guid=asset_group.assets[0].guid, ia_class='test', viewpoint='test'
    )
    sighting = Sighting(stage=SightingStage.identification)
    sighting_assets = SightingAssets(
        sighting_guid=sighting.guid, asset_guid=asset_group.assets[0].guid
    )
    with db.session.begin():
        db.session.add(sighting)
        db.session.add(annotation)
        db.session.add(sighting_assets)
    cleanup(lambda: db.session.delete(sighting_assets))
    cleanup(lambda: db.session.delete(sighting))
    cleanup(lambda: db.session.delete(annotation))

    return asset_group


@pytest.mark.skipif(
    module_unavailable('asset_groups', 'sightings'), reason='AssetGroups module disabled'
)
def test_asset_meta_and_delete(flask_app, db, test_root, admin_user, request):
    from app.modules.annotations.models import Annotation
    from app.modules.assets.models import Asset
    from app.modules.asset_groups.models import AssetGroup
    from app.modules.sightings.models import Sighting, SightingAssets

    asset_group = set_up_assets(flask_app, db, test_root, admin_user, request)

    assert len(asset_group.assets) == 3
    assert len(asset_group.assets[0].annotations) == 1
    assert len(asset_group.assets[0].asset_sightings) == 1
    dim = asset_group.assets[0].get_dimensions()
    assert dim['width'] > 1
    assert dim['height'] > 1
    asset_guids = [a.guid for a in asset_group.assets]
    annotation = asset_group.assets[0].annotations[0]
    sighting = asset_group.assets[0].asset_sightings[0].sighting

    # Delete all assets except the last
    for asset in asset_group.assets[:-1]:
        asset.delete()

    # Assets should be deleted
    assert len(list(asset_group.assets)) == 1
    assert [Asset.query.get(guid) for guid in asset_guids][:-1] == [None, None]
    # Annotations and sighting assets should be deleted
    assert list(SightingAssets.query.filter_by(asset_guid=asset_guids[0])) == []
    assert Annotation.query.get(annotation.guid) is None

    # Sighting and asset group is still around
    assert Sighting.query.get(sighting.guid) is not None
    assert AssetGroup.query.get(asset_group.guid) is not None

    # Delete the last asset should delete the asset group
    asset_group.assets[-1].delete()
    assert AssetGroup.query.get(asset_group.guid) is None


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_update_symlink(test_asset_group_uuid, request):
    from app.modules.asset_groups.models import AssetGroup

    asset_group = AssetGroup.query.get(test_asset_group_uuid)
    zebra = [
        asset
        for asset in asset_group.assets
        if asset.get_original_filename() == 'zebra.jpg'
    ][0]

    symlink = pathlib.Path(zebra.get_symlink())
    assert symlink.is_symlink()
    actual = symlink.resolve()
    assert actual.is_file()
    assert actual.name == zebra.get_original_filename()

    (actual.parent / 'new.txt').touch()
    zebra.update_symlink(str(actual.parent / 'new.txt'))
    # Reset zebra symlink to zebra.jpg
    request.addfinalizer(lambda: zebra.update_symlink(actual))

    new_symlink = pathlib.Path(zebra.get_symlink())
    assert new_symlink.is_symlink()
    assert new_symlink == symlink
    new_actual = symlink.resolve()
    assert new_actual.is_file()
    assert new_actual.name == 'new.txt'


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_derived_images_and_rotation(test_asset_group_uuid, request):
    from app.modules.asset_groups.models import AssetGroup

    asset_group = AssetGroup.query.get(test_asset_group_uuid)
    zebra = [
        asset
        for asset in asset_group.assets
        if asset.get_original_filename() == 'zebra.jpg'
    ][0]

    def get_format_sizes(asset):
        sizes = {}
        for format in asset.FORMATS:
            path = asset.get_or_make_format_path(format)
            with Image.open(path) as im:
                sizes[format] = im.size
        return sizes

    # Image hasn't been rotated, get_original_path() returns the symlink
    assert zebra.get_original_path() == zebra.get_symlink()
    assert zebra.get_dimensions() == {'width': 1000, 'height': 664}
    assert get_format_sizes(zebra) == {
        'master': (1000, 664),
        'mid': (1000, 664),
        'thumb': (256, 170),
    }

    def zebra_cleanup():
        original = zebra.get_original_path()
        original.rename(zebra.get_symlink().resolve())
        zebra.reset_derived_images()

    # Rotate 90 degrees
    zebra.rotate(90)
    request.addfinalizer(zebra_cleanup)
    assert zebra.get_dimensions() == {'width': 664, 'height': 1000}
    assert get_format_sizes(zebra) == {
        'master': (664, 1000),
        'mid': (664, 1000),
        'thumb': (170, 256),
    }

    # Image has been rotated, get_original_path() returns the original
    # image
    assert zebra.get_original_path() != zebra.get_symlink()
    assert zebra.get_original_path().is_file()
    # The original should be still the same
    with Image.open(zebra.get_original_path()) as im:
        assert im.size == (1000, 664)

    # Rotate another 30 degrees (rotating non-90 degree increments
    # doesn't change the image dimensions)
    zebra.rotate(30)
    assert zebra.get_dimensions() == {'width': 664, 'height': 1000}
    assert get_format_sizes(zebra) == {
        'master': (664, 1000),
        'mid': (664, 1000),
        'thumb': (170, 256),
    }

    # The original should be still the same
    with Image.open(zebra.get_original_path()) as im:
        assert im.size == (1000, 664)
