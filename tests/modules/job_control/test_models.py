# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
from unittest import mock

import pytest

import tests.utils as test_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='Asset Group module disabled'
)
def test_job_control(flask_app, researcher_1, test_root, db):
    # pylint: disable=invalid-name
    import uuid

    from app.modules.asset_groups.models import AssetGroup, AssetGroupSighting
    from app.modules.job_control.models import JobControl
    from tests.utils import copy_uploaded_file, create_transaction_dir

    asset_group = None
    try:
        input_filename = 'zippy'
        transaction_id = str(uuid.uuid4())
        trans_dir = create_transaction_dir(flask_app, transaction_id)
        copy_uploaded_file(test_root, input_filename, trans_dir, input_filename)

        asset_group, _ = AssetGroup.create_from_tus(
            'test asset group description',
            researcher_1,
            transaction_id,
            paths=[input_filename],
            foreground=True,
        )

        with db.session.begin():
            sighting_config = test_utils.dummy_sighting_info()
            sighting_config['assetReferences'] = [input_filename]
            ags = AssetGroupSighting(
                asset_group=asset_group,
                sighting_config=sighting_config,
                detection_configs=test_utils.dummy_detection_info(),
            )

            db.session.add(ags)

        ags.setup()

        ags.send_detection_to_sage('african_terrestrial')

        JobControl.check_jobs()

        jobs = JobControl.get_jobs(True)
        assert len(jobs) == 1
        assert jobs[0]['type'] == 'AssetGroupSighting'
        assert jobs[0]['model'] == 'african_terrestrial'
    finally:
        if asset_group:
            asset_group.delete()


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='Asset Group module disabled'
)
@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_check_jobs():
    from app.modules.job_control.models import JobControl

    AssetGroupSighting = 'app.modules.asset_groups.models.AssetGroupSighting'
    Sighting = 'app.modules.sightings.models.Sighting'
    with mock.patch(f'{AssetGroupSighting}.check_jobs') as ags_check_jobs:
        with mock.patch(f'{Sighting}.check_jobs') as s_check_jobs:
            # No errors
            JobControl.check_jobs()
            assert ags_check_jobs.called
            assert s_check_jobs.called

            ags_check_jobs.reset_mock()
            s_check_jobs.reset_mock()

            # AssetGroupSighting.check_jobs raises an error
            ags_check_jobs.side_effect = lambda: 1 / 0
            with pytest.raises(ZeroDivisionError):
                JobControl.check_jobs()
            # Sighting.check_jobs is still called
            assert s_check_jobs.called

            ags_check_jobs.reset_mock()
            s_check_jobs.reset_mock()

            # Both AssetGroupSighting.check_jobs and Sighting.check_jobs raise
            # errors, only the last one is reraised
            s_check_jobs.side_effect = lambda: len(None)
            with pytest.raises(TypeError):
                JobControl.check_jobs()
