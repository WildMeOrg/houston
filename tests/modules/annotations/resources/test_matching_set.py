# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.asset_groups.resources import utils as sub_utils
from tests.modules.encounters.resources import utils as enc_utils
from tests.modules.site_settings.resources import utils as setting_utils
import pytest

from tests.utils import module_unavailable
from tests import utils


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_annotation_matching_set(
    flask_app_client,
    researcher_1,
    admin_user,
    test_clone_asset_group_data,
    request,
    test_root,
):
    # pylint: disable=invalid-name
    from app.modules.annotations.models import Annotation

    sub_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )
    asset_guid = test_clone_asset_group_data['asset_uuids'][0]

    uuids = enc_utils.create_encounter(flask_app_client, researcher_1, request, test_root)
    enc_guid = uuids['encounters'][0]

    tx = setting_utils.get_some_taxonomy_dict(flask_app_client, admin_user)
    assert tx
    assert 'id' in tx
    taxonomy_guid = tx['id']
    locationId = 'erehwon'
    patch_data = [
        utils.patch_replace_op('taxonomy', taxonomy_guid),
        utils.patch_replace_op('locationId', locationId),
    ]
    enc_utils.patch_encounter(
        flask_app_client,
        enc_guid,
        researcher_1,
        patch_data,
    )

    viewpoint = 'upfront'
    response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        asset_guid,
        enc_guid,
        viewpoint=viewpoint,
    )

    annotation_guid = response.json['guid']
    annotation = Annotation.query.get(annotation_guid)
    assert annotation.asset_guid == uuid.UUID(
        test_clone_asset_group_data['asset_uuids'][0]
    )

    criteria = annotation.get_matching_set_default_criteria()
    assert 'viewpoint' in criteria
    assert criteria['viewpoint'] == {
        'front',
        'frontleft',
        'frontright',
        'up',
        'upfront',
        'upfrontleft',
        'upfrontright',
        'upleft',
        'upright',
    }
    assert criteria.get('taxonomy_guid') == taxonomy_guid
    assert criteria.get('encounter_guid_not') == enc_guid

    es_query = Annotation.elasticsearch_criteria_to_query(criteria)
    assert es_query
    assert 'bool' in es_query
