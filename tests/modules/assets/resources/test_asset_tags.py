# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests import utils
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.assets.resources.utils as asset_utils
from tests.modules.keywords.resources import utils as tag_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_tags_on_asset(flask_app_client, researcher_1, test_clone_asset_group_data, db):
    # pylint: disable=invalid-name
    from app.modules.assets.models import Asset
    from app.modules.keywords.models import Keyword as Tag
    from app.modules.keywords.models import KeywordSource as TagSource

    # this gives us an "existing" tag to work with
    tag_value1 = 'TEST_TAG_VALUE_1'
    tag = Tag(value=tag_value1)
    with db.session.begin():
        db.session.add(tag)
    assert tag is not None

    # Clone the known asset_group so that the asset data is in the database
    clone = asset_group_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )

    asset = None
    try:
        asset_guid = clone.asset_group.assets[0].guid
        response = asset_utils.read_asset(flask_app_client, researcher_1, asset_guid)
        asset_guid = response.json['guid']
        asset = Asset.query.get(asset_guid)
        assert asset is not None

        # patch to add *existing* tag
        res = asset_utils.patch_asset(
            flask_app_client,
            asset.guid,
            researcher_1,
            [utils.patch_add_op('tags', str(tag.guid))],
        )
        kw = asset.get_tags()
        assert len(kw) == 1
        assert kw[0].value == tag_value1

        # patch to add *new* tag (by value)
        tag_value2 = 'TEST_TAG_VALUE_2'
        res = asset_utils.patch_asset(
            flask_app_client,
            asset.guid,
            researcher_1,
            [utils.patch_add_op('tags', {'value': tag_value2, 'source': TagSource.user})],
        )
        kw = asset.get_tags()
        assert len(kw) == 2
        # since tag order is arbitrary, we dont know which this is, but should be one of them!
        assert kw[0].value == tag_value2 or kw[1].value == tag_value2

        # patch to add *new* tag (by value) -- except will fail (409) cuz tag exists
        res = asset_utils.patch_asset(
            flask_app_client,
            asset.guid,
            researcher_1,
            [utils.patch_add_op('tags', {'value': tag_value2, 'source': TagSource.user})],
            409,
        )

        # patch to add invalid tag guid
        res = asset_utils.patch_asset(
            flask_app_client,
            asset.guid,
            researcher_1,
            [utils.patch_add_op('tags', '00000000-0000-0000-0000-000000002170')],
            409,
        )

        # patch to remove a tag (only can happen by id)
        res = tag_utils.read_all_keywords(flask_app_client, researcher_1)
        orig_kwct = len(res.json)

        res = asset_utils.patch_asset(
            flask_app_client,
            asset.guid,
            researcher_1,
            [utils.patch_remove_op('tags', str(tag.guid))],
        )
        kw = asset.get_tags()
        assert len(kw) == 1
        assert kw[0].value == tag_value2

        res = tag_utils.read_all_keywords(flask_app_client, researcher_1)
        kwct = len(res.json)
        assert (
            kwct == orig_kwct - 1
        )  # [DEX-347] op=remove above caused deletion of unused tag

        guid = res.json[0]['guid']
        res = asset_utils.patch_asset(
            flask_app_client,
            asset.guid,
            researcher_1,
            [utils.patch_remove_op('tags', str(guid))],
        )

        # the delete_asset above should take the un-reference tag with it [DEX-347], thus:
        res = tag_utils.read_all_keywords(flask_app_client, researcher_1)
        assert len(res.json) == kwct - 1
    finally:
        with db.session.begin():
            for asset in clone.asset_group.assets:
                # Delete the asset
                asset.delete_cascade()
                read_asset = Asset.query.get(asset.guid)
                assert read_asset is None

            for tag in Tag.query.all():
                if tag.value.startswith('TEST_TAG_VALUE_'):
                    db.session.delete(tag)
                    read_tag = Tag.query.get(tag.guid)
                    assert read_tag is None

        clone.cleanup()


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_tags_on_bulk_asset(
    flask_app_client, researcher_1, test_clone_asset_group_data, db
):
    # pylint: disable=invalid-name
    from app.modules.assets.models import Asset
    from app.modules.keywords.models import Keyword as Tag

    # this gives us an "existing" tag to work with
    tag_value1 = 'TEST_TAG_VALUE_3'
    tag1 = Tag(value=tag_value1)
    with db.session.begin():
        db.session.add(tag1)
    assert tag1 is not None

    tag_value2 = 'TEST_TAG_VALUE_4'
    tag2 = Tag(value=tag_value2)
    with db.session.begin():
        db.session.add(tag2)
    assert tag2 is not None

    # Clone the known asset_group so that the asset data is in the database
    clone = asset_group_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )

    assets = []
    try:
        for asset_guid in test_clone_asset_group_data['asset_uuids']:
            response = asset_utils.read_asset(flask_app_client, researcher_1, asset_guid)
            asset_guid = response.json['guid']
            asset = Asset.query.get(asset_guid)
            assert asset is not None
            assets.append(asset)
            kw = asset.get_tags()
            assert len(kw) == 0

        patch_ops = []
        for index, asset in enumerate(assets):
            if index == 0:
                patch_ops.append(
                    utils.patch_add_op('tags', str(tag1.guid), guid=asset.guid)
                )
            elif index == 1:
                # Check if we can assign the same tag twice to the same asset
                patch_ops.append(
                    utils.patch_add_op('tags', str(tag1.guid), guid=asset.guid)
                )
                patch_ops.append(
                    utils.patch_add_op('tags', str(tag2.guid), guid=asset.guid)
                )
            elif index == 2:
                # Check if we can assign the same tag twice to the same asset
                patch_ops.append(
                    utils.patch_add_op('tags', str(tag2.guid), guid=asset.guid)
                )
                patch_ops.append(
                    utils.patch_add_op('tags', str(tag1.guid), guid=asset.guid)
                )
            elif index == 3:
                patch_ops.append(
                    utils.patch_add_op('tags', str(tag2.guid), guid=asset.guid)
                )
            else:
                raise RuntimeError()

        # patch to add *existing* tag
        res = asset_utils.patch_asset_bulk(
            flask_app_client,
            researcher_1,
            patch_ops,
        )

        for index, asset in enumerate(assets):
            kw = asset.get_tags()
            if index == 0:
                assert len(kw) == 1
                assert kw[0].value == tag_value1
            elif index == 1:
                assert len(kw) == 2
                assert kw[0].value == tag_value1
                assert kw[1].value == tag_value2
            elif index == 2:
                assert len(kw) == 2
                assert kw[0].value == tag_value1
                assert kw[1].value == tag_value2
            elif index == 3:
                assert len(kw) == 1
                assert kw[0].value == tag_value2
            else:
                raise RuntimeError()

        # patch to remove a tag (only can happen by id)
        res = tag_utils.read_all_keywords(flask_app_client, researcher_1)
        orig_kwct = len(res.json)

        patch_ops = []
        for index, asset in enumerate(assets):
            if index == 0:
                pass
            elif index == 1:
                # Check if we can assign the same tag twice to the same asset
                patch_ops.append(
                    utils.patch_remove_op('tags', str(tag1.guid), guid=asset.guid)
                )
            elif index == 2:
                # Check if we can assign the same tag twice to the same asset
                patch_ops.append(
                    utils.patch_remove_op('tags', str(tag2.guid), guid=asset.guid)
                )
                patch_ops.append(
                    utils.patch_remove_op('tags', str(tag1.guid), guid=asset.guid)
                )
            elif index == 3:
                patch_ops.append(
                    utils.patch_add_op('tags', str(tag1.guid), guid=asset.guid)
                )
            else:
                raise RuntimeError()

        # patch to remove (and modify) tags
        res = asset_utils.patch_asset_bulk(
            flask_app_client,
            researcher_1,
            patch_ops,
        )

        for index, asset in enumerate(assets):
            kw = asset.get_tags()
            if index == 0:
                assert len(kw) == 1
                assert kw[0].value == tag_value1
            elif index == 1:
                assert len(kw) == 1
                assert kw[0].value == tag_value2
            elif index == 2:
                assert len(kw) == 0
            elif index == 3:
                assert len(kw) == 2
                assert kw[0].value == tag_value1
                assert kw[1].value == tag_value2
            else:
                raise RuntimeError()

        res = tag_utils.read_all_keywords(flask_app_client, researcher_1)
        kwct = len(res.json)
        assert kwct == orig_kwct

        # Remove all tag1 references
        patch_ops = []
        for index, asset in enumerate(assets):
            if index == 0:
                patch_ops.append(
                    utils.patch_remove_op('tags', str(tag1.guid), guid=asset.guid)
                )
            elif index == 1:
                pass
            elif index == 2:
                pass
            elif index == 3:
                patch_ops.append(
                    utils.patch_remove_op('tags', str(tag1.guid), guid=asset.guid)
                )
            else:
                raise RuntimeError()

        # patch to remove (and modify) tags
        res = asset_utils.patch_asset_bulk(
            flask_app_client,
            researcher_1,
            patch_ops,
        )

        for index, asset in enumerate(assets):
            kw = asset.get_tags()
            if index == 0:
                assert len(kw) == 0
            elif index == 1:
                assert len(kw) == 1
                assert kw[0].value == tag_value2
            elif index == 2:
                assert len(kw) == 0
            elif index == 3:
                assert len(kw) == 1
                assert kw[0].value == tag_value2
            else:
                raise RuntimeError()

        res = tag_utils.read_all_keywords(flask_app_client, researcher_1)
        kwct = len(res.json)
        assert kwct == orig_kwct - 1

        # Remove all tag1 references
        patch_ops = []
        for index, asset in enumerate(assets):
            if index == 0:
                pass
            elif index == 1:
                patch_ops.append(
                    utils.patch_remove_op('tags', str(tag2.guid), guid=asset.guid)
                )
            elif index == 2:
                pass
            elif index == 3:
                patch_ops.append(
                    utils.patch_remove_op('tags', str(tag2.guid), guid=asset.guid)
                )
            else:
                raise RuntimeError()

        # patch to remove (and modify) tags
        res = asset_utils.patch_asset_bulk(
            flask_app_client,
            researcher_1,
            patch_ops,
        )

        for index, asset in enumerate(assets):
            kw = asset.get_tags()
            assert len(kw) == 0

        # the delete_asset above should take the un-reference tag with it [DEX-347], thus:
        res = tag_utils.read_all_keywords(flask_app_client, researcher_1)
        assert len(res.json) == kwct - 1

    finally:
        with db.session.begin():
            for asset in clone.asset_group.assets:
                # Delete the asset
                asset.delete_cascade()
                read_asset = Asset.query.get(asset.guid)
                assert read_asset is None

            for tag in Tag.query.all():
                if tag.value.startswith('TEST_TAG_VALUE_'):
                    db.session.delete(tag)
                    read_tag = Tag.query.get(tag.guid)
                    assert read_tag is None

        clone.cleanup()
