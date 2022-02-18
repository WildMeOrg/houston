# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import datetime
from unittest import mock
import tests.utils as test_utils
import pytest
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='Asset Group module disabled'
)
def test_job_control(flask_app, researcher_1, test_root, db):
    # pylint: disable=invalid-name
    from app.modules.asset_groups.models import AssetGroup, AssetGroupSighting
    from app.modules.job_control.models import JobControl
    from app.modules.asset_groups.tasks import sage_detection

    asset_group = None
    try:
        asset_group = AssetGroup(owner_guid=researcher_1.guid)
        ags = AssetGroupSighting(
            asset_group=asset_group,
            sighting_config=test_utils.dummy_sighting_info(),
            detection_configs=test_utils.dummy_detection_info(),
        )

        db.session.add(asset_group)

        with mock.patch('app.modules.asset_groups.models.current_app') as mock_app:
            mock_app.return_value = flask_app
            mock_app.config.get.return_value = 'zebra'
            utc_now = datetime.datetime(2021, 6, 29, 8, 22, 35)
            with mock.patch('datetime.datetime') as mock_datetime:
                mock_datetime.utcnow.return_value = utc_now
                sage_detection(str(ags.guid), 'african_terrestrial')

            # TODO asserts
            JobControl.check_jobs()

            jobs = JobControl.get_jobs(True)
            assert len(jobs) == 1
            assert jobs[0]['type'] == 'AssetGroupSighting'
            assert jobs[0]['model'] == 'african_terrestrial'
    finally:
        if asset_group:
            asset_group.delete()
