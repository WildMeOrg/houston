# -*- coding: utf-8 -*-
import uuid

import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.sightings.resources.utils as sighting_utils
import tests.utils as test_utils

import pytest

from tests.utils import (
    module_unavailable,
    extension_unavailable,
    wait_for_elasticsearch_status,
)


@pytest.mark.skipif(
    module_unavailable('sightings'),
    reason='Sighting module disabled',
)
@pytest.mark.skipif(
    extension_unavailable('elasticsearch'),
    reason='Elasticsearch extension disabled',
)
def test_annotation_identification(
    flask_app,
    flask_app_client,
    researcher_1,
    internal_user,
    test_root,
    db,
    request,
):
    # pylint: disable=invalid-name
    from app.modules.sightings.models import Sighting, SightingStage
    from app.modules.annotations.models import Annotation
    from app.extensions import elasticsearch as es

    if es.is_disabled():
        pytest.skip('Elasticsearch disabled (via command-line)')

    # Create two sightings so that there will be a valid annotation when doing ID for the second one.
    # Otherwise the get_matching_set_data in sightings will return an empty list
    (
        asset_group_uuid1,
        asset_group_sighting_guid1,
        asset_uuid1,
    ) = asset_group_utils.create_simple_asset_group(
        flask_app_client, researcher_1, request, test_root
    )
    target_annot_guid = asset_group_utils.patch_in_dummy_annotation(
        flask_app_client, db, researcher_1, asset_group_sighting_guid1, asset_uuid1
    )
    commit_response = asset_group_utils.commit_asset_group_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid1
    )
    sighting_uuid = commit_response.json['guid']

    # mark it as processed or it won't be valid in the matching set
    sighting_utils.write_sighting_path(
        flask_app_client, researcher_1, f'{sighting_uuid}/reviewed', {}
    )

    # Second sighting, the one we'll use for testing, Create with annotation but don't commit.... yet
    (
        asset_group_uuid2,
        asset_group_sighting_guid2,
        asset_uuid2,
    ) = asset_group_utils.create_simple_asset_group(
        flask_app_client, researcher_1, request, test_root
    )
    query_annot_guid = asset_group_utils.patch_in_dummy_annotation(
        flask_app_client, db, researcher_1, asset_group_sighting_guid2, asset_uuid2
    )
    target_annot = Annotation.query.get(target_annot_guid)
    query_annot = Annotation.query.get(query_annot_guid)
    # content guid allocated by Sage normally but we're simulating sage
    target_annot.content_guid = uuid.uuid4()
    query_annot.content_guid = uuid.uuid4()
    # make annots neighbors
    target_annot.viewpoint = 'up'
    query_annot.viewpoint = 'upright'
    with db.session.begin(subtransactions=True):
        db.session.merge(target_annot)
        db.session.merge(query_annot)

    # this is basically a duplicate of tests/modules/sightings/resources/test_identify_sighting.py
    #   so we dont do a ton of validation here; we are just setting up for an additional test of
    #   single-annotation identification

    id_configs = [
        {
            'algorithms': [
                'hotspotter_nosv',
            ],
        }
    ]
    patch_data = [test_utils.patch_replace_op('idConfigs', id_configs)]
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        asset_group_sighting_guid2,
        patch_data,
    )

    # Start ID simulating success response from Sage
    response = asset_group_utils.commit_asset_group_sighting_sage_identification(
        flask_app, flask_app_client, researcher_1, asset_group_sighting_guid2
    )
    sighting_uuid = response.json['guid']
    wait_for_elasticsearch_status(flask_app_client, researcher_1)

    sighting = Sighting.query.get(sighting_uuid)
    assert sighting.stage == SightingStage.identification
    annotation = sighting.encounters[0].annotations[0]
    num_sent = annotation.send_to_identification()
    assert num_sent == 1
    bad_query = {
        'bool': {
            'filter': [
                {'match': {'encounter_guid': '00000000-0000-0000-0000-badbadbadbad'}}
            ]
        }
    }
    num_sent = annotation.send_to_identification(bad_query)
    assert num_sent == 0
