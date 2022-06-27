# -*- coding: utf-8 -*-
import importlib
from unittest import mock

import pytest
from invoke import MockContext

from tests.modules.asset_groups.resources import utils as ag_utils
from tests.modules.sightings.resources import utils as s_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_print_all_ags_jobs(flask_app_client, researcher_1, request, test_root):
    from app.modules.asset_groups.models import AssetGroupSighting

    ags_guid = ag_utils.create_simple_asset_group(
        flask_app_client, researcher_1, request, test_root
    )[1]
    ags = AssetGroupSighting.query.get(ags_guid)
    assert ags.stage == 'curation'

    with mock.patch('tasks.utils.app_context_task') as app_context_task:
        app_context_task.side_effect = lambda: (lambda func: func)

        import tasks.codex.job_control

        importlib.reload(tasks.codex.job_control)

        print_all_ags_jobs = tasks.codex.job_control.print_all_ags_jobs

        with mock.patch.object(ags, 'get_jobs_debug') as get_jobs_debug:
            print_all_ags_jobs(MockContext(), ags_guid=ags_guid)
            assert get_jobs_debug.call_count == 1
            get_jobs_debug.reset_mock()

            print_all_ags_jobs(MockContext())
            assert get_jobs_debug.call_count == 0


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_print_all_sighting_jobs(flask_app_client, researcher_1, request, test_root):
    from app.modules.sightings.models import Sighting

    s_guid = s_utils.create_sighting(flask_app_client, researcher_1, request, test_root)[
        'sighting'
    ]
    sighting = Sighting.query.get(s_guid)
    assert sighting.stage == 'processed'

    with mock.patch('tasks.utils.app_context_task') as app_context_task:
        app_context_task.side_effect = lambda: (lambda func: func)

        import tasks.codex.job_control

        importlib.reload(tasks.codex.job_control)

        print_all_sighting_jobs = tasks.codex.job_control.print_all_sighting_jobs

        with mock.patch.object(sighting, 'get_job_debug') as get_job_debug:
            print_all_sighting_jobs(MockContext(), sighting_guid=s_guid)
            assert get_job_debug.call_count == 1
            get_job_debug.reset_mock()
