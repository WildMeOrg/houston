# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests import utils
from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.asset_groups.resources import utils as sub_utils
from tests.modules.keywords.resources import utils as keyword_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_keywords_on_annotation(
    flask_app_client, researcher_1, test_clone_asset_group_data, db
):
    # pylint: disable=invalid-name
    from app.modules.assets.models import Asset
    from app.modules.annotations.models import Annotation
    from app.modules.keywords.models import Keyword, KeywordSource

    # this gives us an "existing" keyword to work with
    keyword_value1 = 'TEST_KEYWORD_VALUE_1'
    keyword = Keyword(value=keyword_value1)
    with db.session.begin():
        db.session.add(keyword)
    assert keyword is not None

    clone = sub_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )

    response = annot_utils.create_annotation_simple(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_uuids'][0],
    )

    annotation_guid = response.json['guid']
    annotation = Annotation.query.get(annotation_guid)
    assert annotation is not None

    # patch to add *existing* keyword
    res = annot_utils.patch_annotation(
        flask_app_client,
        annotation.guid,
        researcher_1,
        [utils.patch_add_op('keywords', str(keyword.guid))],
    )
    kw = annotation.get_keywords()
    assert len(kw) == 1
    assert kw[0].value == keyword_value1

    # patch to add *new* keyword (by value)
    keyword_value2 = 'TEST_KEYWORD_VALUE_2'
    res = annot_utils.patch_annotation(
        flask_app_client,
        annotation.guid,
        researcher_1,
        [
            utils.patch_add_op(
                'keywords', {'value': keyword_value2, 'source': KeywordSource.user}
            )
        ],
    )
    kw = annotation.get_keywords()
    assert len(kw) == 2
    # since keyword order is arbitrary, we dont know which this is, but should be one of them!
    assert kw[0].value == keyword_value2 or kw[1].value == keyword_value2

    # patch to add *new* keyword (by value) -- except will fail (409) cuz keyword exists
    res = annot_utils.patch_annotation(
        flask_app_client,
        annotation.guid,
        researcher_1,
        [
            utils.patch_add_op(
                'keywords', {'value': keyword_value2, 'source': KeywordSource.user}
            )
        ],
        409,
    )

    # patch to add invalid keyword guid
    res = annot_utils.patch_annotation(
        flask_app_client,
        annotation.guid,
        researcher_1,
        [utils.patch_add_op('keywords', '00000000-0000-0000-0000-000000002170')],
        409,
    )

    # patch to remove a keyword (only can happen by id)
    res = keyword_utils.read_all_keywords(flask_app_client, researcher_1)
    orig_kwct = len(res.json)

    res = annot_utils.patch_annotation(
        flask_app_client,
        annotation.guid,
        researcher_1,
        [utils.patch_remove_op('keywords', str(keyword.guid))],
    )
    kw = annotation.get_keywords()
    assert len(kw) == 1
    assert kw[0].value == keyword_value2

    res = keyword_utils.read_all_keywords(flask_app_client, researcher_1)
    kwct = len(res.json)
    assert (
        kwct == orig_kwct - 1
    )  # [DEX-347] op=remove above caused deletion of unused keyword

    # And deleting it
    annot_utils.delete_annotation(flask_app_client, researcher_1, annotation_guid)
    read_annotation = Annotation.query.get(annotation_guid)
    assert read_annotation is None

    # the delete_annotation above should take the un-reference keyword with it [DEX-347], thus:
    res = keyword_utils.read_all_keywords(flask_app_client, researcher_1)
    assert len(res.json) == kwct - 1

    with db.session.begin():
        for asset in clone.asset_group.assets:
            # Delete the asset
            asset.delete_cascade()
            read_asset = Asset.query.get(asset.guid)
            assert read_asset is None

        for keyword in Keyword.query.all():
            if keyword.value.startswith('TEST_KEYWORD_VALUE_'):
                db.session.delete(keyword)
                read_keyword = Keyword.query.get(keyword.guid)
                assert read_keyword is None

    clone.cleanup()
