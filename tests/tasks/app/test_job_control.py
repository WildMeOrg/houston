# -*- coding: utf-8 -*-
import io
from unittest import mock
import tests.extensions.tus.utils as tus_utils
import tests.modules.asset_groups.resources.utils as asset_group_utils

from invoke import MockContext
import pytest

from tests.utils import module_unavailable


# Check that the task methods for the asset control job tasks print the correct output
@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_asset_group_detection_jobs(
    flask_app, flask_app_client, researcher_1, staff_user, test_root, db
):
    # pylint: disable=invalid-name

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None
    try:
        data = asset_group_utils.AssetGroupCreationData(transaction_id, test_filename)
        data.set_field('speciesDetectionModel', ['african_terrestrial'])

        # Simulate a valid response from Sage but don't actually send the request to Sage
        with mock.patch.object(
            flask_app.acm,
            'request_passthrough_result',
            return_value={'success': True},
        ):
            resp = asset_group_utils.create_asset_group(
                flask_app_client, None, data.get()
            )
            asset_group_uuid = resp.json['guid']

        # Now see that the task gets what we expect
        with mock.patch('app.create_app'):
            with mock.patch('sys.stdout', new=io.StringIO()) as stdout:
                from tasks.app import job_control

                job_control.print_all_asset_jobs(
                    MockContext(), resp.json['assets'][0]['guid']
                )
                job_output = stdout.getvalue()
                assert 'Job ' in job_output
                assert 'Active:True Started (UTC)' in job_output
                assert 'model:african_terrestrial' in job_output

                # Simulate a valid response from Sage but don't actually send the request to Sage
                with mock.patch.object(
                    flask_app.acm,
                    'request_passthrough_result',
                    return_value={'success': True, 'content': 'something'},
                ):
                    job_control.print_last_asset_job(
                        MockContext(), resp.json['assets'][0]['guid'], verbose=True
                    )
                    job_output = stdout.getvalue()
                    assert 'Job ' in job_output
                    assert 'Active:True Started (UTC)' in job_output
                    assert 'model:african_terrestrial' in job_output
                    assert "Request:{'endpoint': '/api/engine/detect" in job_output
                    assert (
                        "Response:{'success': True, 'content': 'something'}" in job_output
                    )
    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, staff_user, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(transaction_id)


# Check that the task methods for the sighting job tasks print the correct output
@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_sighting_identification_jobs(
    flask_app,
    flask_app_client,
    researcher_1,
    test_root,
    db,
    request,
):
    # pylint: disable=invalid-name
    from app.modules.sightings.models import Sighting, SightingStage

    # Create two sightings so that there will be a valid annotation when doing ID for the second one.
    # Otherwise the get_matching_set_data in sightings will return an empty list
    (
        asset_group_uuid1,
        asset_group_sighting_guid1,
        asset_uuid1,
    ) = asset_group_utils.create_simple_asset_group(
        flask_app_client, researcher_1, request, test_root
    )
    asset_group_utils.patch_in_dummy_annotation(
        flask_app_client, db, researcher_1, asset_group_sighting_guid1, asset_uuid1
    )
    commit_response = asset_group_utils.commit_asset_group_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid1
    )
    sighting_uuid = commit_response.json['guid']

    # Fake it being all the way though to processed or it won't be valid in the matching set
    sighting = Sighting.query.get(sighting_uuid)
    sighting.stage = SightingStage.processed

    # Second sighting, the one we'll use for testing
    (
        asset_group_uuid2,
        asset_group_sighting_guid2,
        asset_uuid2,
    ) = asset_group_utils.create_simple_asset_group(
        flask_app_client, researcher_1, request, test_root
    )
    annot_uuid = asset_group_utils.patch_in_dummy_annotation(
        flask_app_client, db, researcher_1, asset_group_sighting_guid2, asset_uuid2
    )
    response = asset_group_utils.commit_asset_group_sighting_sage_identification(
        flask_app, flask_app_client, researcher_1, asset_group_sighting_guid2
    )
    sighting_uuid = response.json['guid']

    # Here starts the test for real
    sighting = Sighting.query.get(sighting_uuid)
    # Push stage back to ID
    sighting.stage = SightingStage.identification

    # Now give it an ID config
    sighting.id_configs = [
        {
            'algorithms': [
                'hotspotter_nosv',
            ],
            'matchingSetDataOwners': 'mine',
        }
    ]

    with mock.patch.object(
        flask_app.acm,
        'request_passthrough_result',
        return_value={'success': True},
    ):
        from app.modules.sightings import tasks

        with mock.patch.object(
            tasks.send_identification,
            'delay',
            side_effect=lambda *args, **kwargs: tasks.send_identification(
                *args, **kwargs
            ),
        ):
            sighting.ia_pipeline()

    # Now see that the task gets what we expect
    with mock.patch('app.create_app'):
        with mock.patch('sys.stdout', new=io.StringIO()) as stdout:
            from tasks.app import job_control

            job_control.print_all_annotation_jobs(MockContext(), str(annot_uuid))
            job_output = stdout.getvalue()
            assert 'Job ' in job_output
            assert 'Active:True Started (UTC)' in job_output
            assert 'algorithm:hotspotter_nosv' in job_output

            # Simulate a valid response from Sage but don't actually send the request to Sage
            with mock.patch.object(
                flask_app.acm,
                'request_passthrough_result',
                return_value={'success': True, 'content': 'something'},
            ):
                job_control.print_last_annotation_job(
                    MockContext(), str(annot_uuid), verbose=True
                )
                job_output = stdout.getvalue()
                assert 'Job ' in job_output
                assert 'Active:True Started (UTC)' in job_output
                assert 'algorithm:hotspotter_nosv' in job_output
                assert "Request:{'jobid': " in job_output
                assert "Response:{'success': True, 'content': 'something'}" in job_output
