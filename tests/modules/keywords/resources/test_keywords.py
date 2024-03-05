# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

import tests.modules.keywords.resources.utils as keyword_utils
from app.modules.keywords.models import Keyword
from tests import utils as test_utils


def test_get_keyword_not_found(flask_app_client, researcher_1):
    keyword_utils.read_keyword(flask_app_client, None, str(uuid.uuid4()), 401)
    keyword_utils.read_keyword(flask_app_client, researcher_1, str(uuid.uuid4()), 404)


def test_create_keyword(db, flask_app_client, researcher_1):
    orig_ct = test_utils.row_count(db, Keyword)
    val = 'test_keyword_0'
    response = keyword_utils.create_keyword(flask_app_client, researcher_1, val)
    assert response.json.get('value', None) == val
    assert test_utils.row_count(db, Keyword) == orig_ct + 1

    # anon should *not* be able to create/write
    response = keyword_utils.create_keyword(
        flask_app_client, None, 'keyword_fail', expected_status_code=403
    )
    assert test_utils.row_count(db, Keyword) == orig_ct + 1

    # this should fail due to non-uniqueness (conflict/409)
    response = keyword_utils.create_keyword(
        flask_app_client, researcher_1, val, expected_status_code=409
    )

    # this should fail due to invalid source (422)
    response = keyword_utils.create_keyword(
        flask_app_client, researcher_1, 'FAIL', source='FAIL', expected_status_code=422
    )


def test_read_all_keywords(db, flask_app_client, researcher_1, staff_user):
    orig_ct = test_utils.row_count(db, Keyword)
    keyword_utils.create_keyword(
        flask_app_client, researcher_1, 'list_test'
    )  # lets have at least one
    response = keyword_utils.read_all_keywords(flask_app_client, None)
    assert len(response.json) == orig_ct + 1

    # Clean-up
    for keyword in response.json:
        guid = keyword.get('guid', None)
        keyword_utils.delete_keyword(flask_app_client, staff_user, guid)


def test_modify_keyword(db, flask_app_client, researcher_1, staff_user):
    orig_ct = test_utils.row_count(db, Keyword)
    val1 = 'test_keyword_1'
    response = keyword_utils.create_keyword(flask_app_client, researcher_1, val1)
    guid = response.json.get('guid', None)
    assert guid
    assert response.json.get('value', None) == val1
    assert test_utils.row_count(db, Keyword) == orig_ct + 1
    response = keyword_utils.read_keyword(flask_app_client, researcher_1, guid)
    assert guid == response.json.get('guid', None)
    assert response.json.get('value', None) == val1

    # patch and verify
    val2 = 'test_keyword_2'
    patch = [{'op': 'replace', 'path': '/value', 'value': val2}]
    response = keyword_utils.patch_keyword(flask_app_client, staff_user, guid, patch)
    assert response.json.get('value', None) == val2
    # doublecheck by reading back in
    response = keyword_utils.read_keyword(flask_app_client, researcher_1, guid)
    assert response.json.get('value', None) == val2
    assert response.json.get('usageCount', None) == 0

    # both of these should not be allowed (403)
    response = keyword_utils.patch_keyword(
        flask_app_client, researcher_1, guid, patch, 403
    )
    response = keyword_utils.delete_keyword(flask_app_client, researcher_1, guid, 403)

    # should not be allowed to patch source (422)
    patch = [{'op': 'replace', 'path': '/source', 'value': 'user'}]
    response = keyword_utils.patch_keyword(flask_app_client, staff_user, guid, patch, 422)

    # should successfully kill this
    response = keyword_utils.delete_keyword(flask_app_client, staff_user, guid)
    assert orig_ct == test_utils.row_count(db, Keyword)


# create 2 asset
# create 2 annotation
# create 2 keyword
# add keyword to asset
# add keyword to annotation
# merge keyword
# check keyword is added to annotation
# check keyword is added to asset
# check keyword is deleted


def test_merge_keyword(
    db, flask_app_client, researcher_1, staff_user, request, test_root
):
    #     # pylint: disable=invalid-name
    import logging
    from uuid import UUID

    import tests.modules.assets.resources.utils as asset_utils
    from app.modules.annotations.models import Annotation
    from app.modules.assets.models import Asset
    from app.modules.keywords.models import Keyword
    from app.modules.keywords.models import Keyword as Tag
    from tests import utils
    from tests.modules.annotations.resources import utils as annot_utils
    from tests.modules.asset_groups.resources import utils as asset_group_utils

    log = logging.getLogger(__name__)  # pylint: disable=invalid-name

    # Create two keywords
    val1 = 'test_keyword_1'
    val2 = 'test_keyword_2'
    response1 = keyword_utils.create_keyword(flask_app_client, researcher_1, val1)
    response2 = keyword_utils.create_keyword(flask_app_client, researcher_1, val2)
    guid1 = response1.json.get('guid', None)
    guid2 = response2.json.get('guid', None)
    assert guid1
    assert guid2

    # Create two assets
    uuids1 = asset_group_utils.create_simple_asset_group_uuids(
        flask_app_client, researcher_1, request, test_root
    )
    asset_guid1 = uuids1['assets'][0]
    response1 = asset_utils.read_asset(flask_app_client, researcher_1, asset_guid1)
    asset_guid1 = response1.json['guid']
    asset1 = Asset.query.get(asset_guid1)
    assert asset1 is not None
    tag1 = Tag.query.get(guid1)
    if tag1 is not None:
        asset1.add_tag(tag1)
        tags1 = asset1.get_tags()
        assert tag1 in tags1
    else:
        log.info('tag1 is None')

    uuids2 = asset_group_utils.create_simple_asset_group_uuids(
        flask_app_client, researcher_1, request, test_root
    )
    asset_guid2 = uuids2['assets'][0]
    response2 = asset_utils.read_asset(flask_app_client, researcher_1, asset_guid2)
    asset_guid2 = response2.json['guid']
    asset2 = Asset.query.get(asset_guid2)
    assert asset2 is not None
    tag2 = Tag.query.get(guid2)
    if tag2 is not None:
        asset2.add_tag(tag2)
        tags2 = asset2.get_tags()
        assert tag2 in tags2
    else:
        log.info('tag2 is None')
    # Create two annotations
    response1 = annot_utils.create_annotation_simple(
        flask_app_client, researcher_1, asset_guid1
    )
    response2 = annot_utils.create_annotation_simple(
        flask_app_client, researcher_1, asset_guid2
    )
    annotation_guid1 = response1.json['guid']
    annotation_guid2 = response2.json['guid']
    annotation1 = Annotation.query.get(annotation_guid1)
    assert annotation1 is not None
    annotation2 = Annotation.query.get(annotation_guid2)
    assert annotation2 is not None
    # Add the first keyword to the first annotation
    res1 = annot_utils.patch_annotation(
        flask_app_client,
        annotation1.guid,
        researcher_1,
        [utils.patch_add_op('keywords', str(guid1))],
    )
    assert res1.status_code == 200

    # Add the second keyword to the second annotation
    res2 = annot_utils.patch_annotation(
        flask_app_client,
        annotation2.guid,
        researcher_1,
        [utils.patch_add_op('keywords', str(guid2))],
    )
    assert res2.status_code == 200

    # Merge the two keywords
    response = keyword_utils.merge_keyword(flask_app_client, researcher_1, guid1, guid2)
    assert response.status_code == 200

    # Read the keyword with guid2, into which guid1 has been merged into
    merged_keyword = Keyword.query.get(guid2)
    assert merged_keyword

    # Check that the first keyword (guid1) no longer exists
    deleted_keyword = Keyword.query.get(guid1)
    assert deleted_keyword is None

    # Verify that the keyword was added to the annotation
    result = [kw.guid for kw in annotation1.get_keywords()]
    assert UUID(guid2) in result
    # Verify that the keyword was addes to asset
    asset = Asset.query.get(asset_guid2)
    tags = asset.get_tags()
    assert merged_keyword in tags
