# -*- coding: utf-8 -*-
import io
from unittest import mock
import tests.extensions.tus.utils as tus_utils
import tests.modules.asset_groups.resources.utils as asset_group_utils

from invoke import MockContext


# Check that the task methods for the asset control job tasks print the correct output
def test_asset_group_detection_jobs(
    flask_app, flask_app_client, researcher_1, staff_user, test_root, db
):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData
    from tests import utils as test_utils

    orig_objs = test_utils.all_count(db)

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None
    try:
        data = TestCreationData(transaction_id)
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
        assert orig_objs == test_utils.all_count(db)
