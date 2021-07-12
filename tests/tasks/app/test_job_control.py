# -*- coding: utf-8 -*-
import io
import uuid
from unittest import mock
import tests.extensions.tus.utils as tus_utils
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.sightings.resources.utils as sighting_utils

from invoke import MockContext


# Check that the task methods for the asset control job tasks print the correct output
def test_asset_group_detection_jobs(
    flask_app, flask_app_client, researcher_1, staff_user, test_root, db
):
    # pylint: disable=invalid-name

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None
    try:
        data = asset_group_utils.TestCreationData(transaction_id)
        data.add_filename(0, test_filename)
        data.set_field('speciesDetectionModel', ['someSortOfModel'])

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
                assert 'model:someSortOfModel' in job_output

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
                    assert 'model:someSortOfModel' in job_output
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
def test_sighting_identification_jobs(
    flask_app,
    flask_app_client,
    researcher_1,
    test_root,
    db,
):
    # pylint: disable=invalid-name
    from app.modules.sightings.models import Sighting, SightingStage

    asset_group_uuids = []
    sighting_uuids = []
    transactions = []
    try:
        # Create two sightings so that there will be a valid annotation when doing ID for the second one.
        # Otherwise the get_matching_set_data in sightings will return an empty list
        transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
        (
            asset_group_uuid,
            sighting_uuid,
            annot_uuid,
        ) = asset_group_utils.create_and_commit_asset_group(
            flask_app_client, db, researcher_1, transaction_id, test_filename
        )
        asset_group_uuids.append(asset_group_uuid)
        sighting_uuids.append(sighting_uuid)
        transactions.append(transaction_id)
        # Fake it being all the way though to processed or it won't be valid in the matching set
        sighting = Sighting.query.get(sighting_uuid)
        sighting.stage = SightingStage.processed

        # Second sighting, the one well use for testing
        transaction_id, test_filename = tus_utils.prep_tus_dir(
            test_root, str(uuid.uuid4())
        )
        (
            asset_group_uuid,
            sighting_uuid,
            annot_uuid,
        ) = asset_group_utils.create_and_commit_asset_group(
            flask_app_client, db, researcher_1, transaction_id, test_filename
        )
        asset_group_uuids.append(asset_group_uuid)
        sighting_uuids.append(sighting_uuid)
        transactions.append(transaction_id)

        # Here starts the test for real
        sighting = Sighting.query.get(sighting_uuid)
        # Push stage back to ID
        sighting.stage = SightingStage.identification

        id_configs = [
            {
                'algorithms': [
                    'noddy',
                ],
                'matchingSetDataOwners': 'mine',
            }
        ]
        with mock.patch.object(
            flask_app.acm,
            'request_passthrough_result',
            return_value={'success': True},
        ):
            sighting.ia_pipeline(id_configs)

        # Now see that the task gets what we expect
        with mock.patch('app.create_app'):
            with mock.patch('sys.stdout', new=io.StringIO()) as stdout:
                from tasks.app import job_control

                job_control.print_all_annotation_jobs(MockContext(), str(annot_uuid))
                job_output = stdout.getvalue()
                assert 'Job ' in job_output
                assert 'Active:True Started (UTC)' in job_output
                assert 'algorithm:noddy' in job_output

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
                    assert 'algorithm:noddy' in job_output
                    assert "Request:{'jobid': " in job_output
                    assert (
                        "Response:{'success': True, 'content': 'something'}" in job_output
                    )
    finally:
        for group in asset_group_uuids:
            asset_group_utils.delete_asset_group(flask_app_client, researcher_1, group)
        for sighting_uuid in sighting_uuids:
            sighting_utils.delete_sighting(flask_app_client, researcher_1, sighting_uuid)
        for trans in transactions:
            tus_utils.cleanup_tus_dir(trans)
