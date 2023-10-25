# -*- coding: utf-8 -*-
import uuid

import pytest

import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.sightings.resources.utils as sighting_utils
import tests.utils as test_utils
from tests.utils import (
    extension_unavailable,
    module_unavailable,
    wait_for_elasticsearch_status,
)


def validate_id_response(flask_app_client, user, sighting):
    from app.modules.sightings.models import SightingStage

    assert all(not job['active'] for job in sighting.jobs.values())
    assert sighting.stage == SightingStage.un_reviewed

    path = f'{str(sighting.guid)}/id_result'

    id_data_resp = sighting_utils.read_sighting_path(flask_app_client, user, path)
    id_data = id_data_resp.json
    assert id_data['query_annotations'][0]['status'] == 'complete'
    assert id_data['query_annotations'][0]['guid'] in id_data['annotation_data'].keys()
    assert (
        id_data['query_annotations'][0]['algorithms']['hotspotter_nosv'][
            'scores_by_annotation'
        ][0]['guid']
        in id_data['annotation_data'].keys()
    )

    first_annot_key = next(iter(id_data['annotation_data']))
    first_annot = id_data['annotation_data'][first_annot_key]

    assert 'sighting_guid' in first_annot
    assert 'sighting_time' in first_annot
    assert 'encounter_guid' in first_annot
    assert 'asset_filename' in first_annot
    assert 'sighting_time_specificity' in first_annot


@pytest.mark.skipif(
    module_unavailable('sightings'),
    reason='Sighting module disabled',
)
@pytest.mark.skipif(
    extension_unavailable('elasticsearch'),
    reason='Elasticsearch extension disabled',
)
def test_sighting_identification(
    flask_app,
    flask_app_client,
    researcher_1,
    internal_user,
    staff_user,
    test_root,
    db,
    request,
):
    # pylint: disable=invalid-name
    from app.extensions import elasticsearch as es
    from app.modules.annotations.models import Annotation
    from app.modules.sightings.models import Sighting, SightingStage

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
    # NOTE this api is deprecated and doesnt seem to affect matching set
    # sighting_utils.write_sighting_path(
    # flask_app_client, researcher_1, f'{sighting_uuid}/reviewed', {}
    # )

    # Second sighting, the one we'll use for testing, Create with annotation but don't commit.... yet
    (
        asset_group_uuid2,
        asset_group_sighting_guid2,
        asset_uuid2,
    ) = asset_group_utils.create_simple_asset_group(
        flask_app_client, researcher_1, request, test_root
    )
    query_annot_guid = asset_group_utils.patch_in_dummy_annotation(
        flask_app_client,
        db,
        researcher_1,
        asset_group_sighting_guid2,
        asset_uuid2,
        padding=1,
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
    print(
        f'>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> {target_annot} {query_annot} <<<<<<<<<<<<<<<<<'
    )

    # Here starts the test for real
    # Create ID config and patch it in
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

    # Check the jobs api give correct data
    jobs_data = sighting_utils.read_sighting_path(
        flask_app_client, staff_user, f'jobs/{sighting_uuid}'
    ).json
    assert len(jobs_data) == 1
    assert (
        set(
            {
                'matching_set',
                'algorithm',
                'annotation',
                'active',
                'start',
                'type',
                'object_guid',
                'job_id',
                'request',
                'response',
            }
        )
        >= jobs_data[0].keys()
    )

    # Make sure the correct job is created and get ID
    job_uuids = [guid for guid in sighting.jobs.keys()]
    assert len(job_uuids) == 1
    job_uuid = job_uuids[0]
    assert sighting.jobs[job_uuid]['algorithm'] == 'hotspotter_nosv'

    progress_guids = []
    for annotation in sighting.get_annotations():
        if annotation.progress_identification:
            if annotation.progress_identification.sage_guid:
                progress_guids.append(str(annotation.progress_identification.guid))

    test_utils.wait_for_progress(flask_app, progress_guids)

    # This is what the FE sends and it is process (now) by the BE but is not yet a valid test as this does not
    # result in ID being rerun.
    rerun_id_data = [
        {
            'algorithms': ['hotspotter_nosv'],
            'matching_set': {
                'bool': {
                    'filter': [
                        {
                            'bool': {
                                'minimum_should_match': 1,
                                'should': [
                                    {
                                        'term': {
                                            'locationId': 'c74ff3e3-d0f5-4930-8c3a-68f2b172b655'
                                        }
                                    }
                                ],
                            }
                        },
                        {'bool': '_MACRO_annotation_neighboring_viewpoints_clause'},
                        {'exists': {'field': 'encounter_guid'}},
                    ],
                    'must_not': {
                        'match': {'encounter_guid': '_MACRO_annotation_encounter_guid'}
                    },
                }
            },
        }
    ]

    sighting_utils.write_sighting_path(
        flask_app_client, researcher_1, f'{sighting_uuid}/rerun_id', rerun_id_data
    )
