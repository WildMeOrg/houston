# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import datetime
from unittest import mock


def test_job_control(flask_app, researcher_1, test_root, db):
    # pylint: disable=invalid-name
    from app.modules.asset_groups.models import AssetGroup, AssetGroupSighting
    from app.modules.job_control.models import JobControl
    from app.modules.asset_groups.tasks import sage_detection

    asset_group = AssetGroup(owner_guid=researcher_1.guid)
    ags = AssetGroupSighting(
        asset_group_guid=asset_group.guid, config={'assetReferences': []}
    )

    db.session.add(asset_group)
    db.session.add(ags)

    with mock.patch(
        'app.modules.asset_groups.models.current_app', return_value=flask_app
    ):
        utc_now = datetime.datetime(2021, 6, 29, 8, 22, 35)
        with mock.patch('datetime.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = utc_now
            sage_detection(str(ags.guid), 'Animal')
        job_id = list(ags.jobs.keys())[0]

        # TODO asserts
        JobControl.check_jobs()

        with mock.patch('app.modules.asset_groups.models.log') as log:
            JobControl.print_jobs()
            assert log.warning.call_args_list, [
                mock.call(
                    f'AssetGroupSighting:{ags.guid} Job:{job_id} Model:Animal UTC Start:{utc_now}'
                ),
            ]

    asset_group.delete()
