# -*- coding: utf-8 -*-
import pathlib
import shutil
from unittest import mock
import uuid


def set_up_assets(flask_app, db, test_root, admin_user, request):
    from app.modules.annotations.models import Annotation
    from app.modules.asset_groups.models import AssetGroup
    from app.modules.asset_groups.metadata import CreateAssetGroupMetadata
    from app.modules.sightings.models import Sighting, SightingAssets, SightingStage

    from tests.modules.asset_groups.resources.utils import TestCreationData

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
    data = TestCreationData(transaction_id)
    data.set_sighting_field(-1, 'assetReferences', [jpg.name for jpg in jpgs])
    metadata = CreateAssetGroupMetadata(data.get())
    with mock.patch(
        'app.modules.asset_groups.metadata.current_user', return_value=admin_user
    ):
        metadata.process_request()
    asset_group = AssetGroup.create_from_metadata(metadata)
    cleanup(lambda: db.session.delete(asset_group))

    # Create annotation and sighting and sighting assets for the first asset
    annotation = Annotation(asset_guid=asset_group.assets[0].guid, ia_class='test')
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


def test_asset_delete(flask_app, db, test_root, admin_user, request):
    from app.modules.annotations.models import Annotation
    from app.modules.assets.models import Asset
    from app.modules.asset_groups.models import AssetGroup
    from app.modules.sightings.models import Sighting, SightingAssets

    asset_group = set_up_assets(flask_app, db, test_root, admin_user, request)

    assert len(asset_group.assets) == 3
    assert len(asset_group.assets[0].annotations) == 1
    assert len(asset_group.assets[0].asset_sightings) == 1
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
