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

    from app.modules.site_settings.models import Regions

    top_id = 'top'
    loc1 = 'location-1'
    parent1 = 'A-1'
    loc2 = 'location-2'
    parent2 = 'B-2'
    parent3 = 'B-3'
    regions_test_data = {
        'id': top_id,
        'locationID': [
            {
                'id': parent1,
                'locationID': [
                    {
                        'id': loc1,
                    }
                ],
            },
            {
                'id': parent2,
                'locationID': [
                    {
                        'id': parent3,
                        'locationID': [
                            {
                                'id': loc2,
                            },
                            {
                                # duplicate, just to suck
                                'id': parent1,
                            },
                        ],
                    }
                ],
            },
        ],
    }
    regions = Regions(data=regions_test_data)

    assert not regions.find('fail')
    found = regions.find()
    assert len(found) == 6
    assert found == {top_id, loc1, loc2, parent1, parent2, parent3}
    found = regions.find(id_only=False)
    assert len(found) == 7  # cuz of duplicate parent1

    # second one is len=2 since we find both matching nodes
    assert len(regions.find(parent1)) == 1
    assert len(regions.find(parent1, id_only=False)) == 2

    assert not regions.full_path('fail')
    assert regions.full_path(loc1) == [top_id, parent1, loc1]
    assert regions.full_path(loc2) == [top_id, parent2, parent3, loc2]

    ancestors = regions.with_ancestors([loc1, loc2])
    assert ancestors == {top_id, parent1, parent2, parent3, loc1, loc2}

    criteria = {
        'locationId': loc1,  # test single value
    }
    es_query = Annotation.elasticsearch_criteria_to_query(criteria)
    assert es_query
    assert (
        es_query['bool']['filter'][0]['bool']['should'][0]['term']['locationId'] == loc1
    )

    criteria = {
        'locationId': [loc1, loc2],  # list of locations
    }
    es_query = Annotation.elasticsearch_criteria_to_query(criteria)
    assert es_query
    locs = [
        term['term']['locationId']
        for term in es_query['bool']['filter'][0]['bool']['should']
    ]
    assert set(locs) == {loc1, loc2}
