# -*- coding: utf-8 -*-
import uuid
from unittest import mock
import tests.extensions.tus.utils as tus_utils
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.sightings.resources.utils as sighting_utils
import tests.utils as test_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_sighting_identification(
    flask_app,
    flask_app_client,
    researcher_1,
    internal_user,
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

        # Second sighting, the one we'll use for testing, Create with annotation but don't commit.... yet
        transaction_id, test_filename = tus_utils.prep_tus_dir(
            test_root, str(uuid.uuid4())
        )
        (
            asset_group_uuid,
            asset_group_sighting_uuid,
            annot_uuid,
        ) = asset_group_utils.create_asset_group_with_annotation(
            flask_app_client, db, researcher_1, transaction_id, test_filename
        )

        asset_group_uuids.append(asset_group_uuid)
        transactions.append(transaction_id)

        # Here starts the test for real
        # Create ID config and patch it in
        id_configs = [
            {
                'algorithms': ['hotspotter_nosv'],
                'matchingSetDataOwners': 'mine',
            }
        ]
        patch_data = [test_utils.patch_replace_op('idConfigs', id_configs)]
        asset_group_utils.patch_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting_uuid, patch_data
        )

        # Start ID simulating success response from Sage
        with mock.patch.object(
            flask_app.acm,
            'request_passthrough_result',
            return_value={'success': True},
        ):
            response = asset_group_utils.commit_asset_group_sighting(
                flask_app_client, researcher_1, asset_group_sighting_uuid
            )
            sighting_uuid = response.json['guid']
            sighting_uuids.append(sighting_uuid)
            sighting = Sighting.query.get(sighting_uuid)

        assert sighting.stage == SightingStage.identification

        # Make sure the correct job is created and get ID
        job_uuids = [guid for guid in sighting.jobs.keys()]
        assert len(job_uuids) == 1
        job_uuid = job_uuids[0]
        assert sighting.jobs[job_uuid]['algorithm'] == 'hotspotter_nosv'

        # Simulate response from Sage
        sage_resp = sighting_utils.build_sage_identification_response(
            job_uuid,
            sighting.jobs[job_uuid]['annotation'],
            sighting.jobs[job_uuid]['algorithm'],
        )

        sighting_utils.send_sage_identification_response(
            flask_app_client,
            internal_user,
            sighting_uuid,
            job_uuid,
            sage_resp,
        )
        assert all(not job['active'] for job in sighting.jobs.values())
        assert sighting.stage == SightingStage.un_reviewed

    finally:
        for group in asset_group_uuids:
            asset_group_utils.delete_asset_group(flask_app_client, researcher_1, group)
        for sighting_uuid in sighting_uuids:
            sighting_utils.delete_sighting(flask_app_client, researcher_1, sighting_uuid)
        for trans in transactions:
            tus_utils.cleanup_tus_dir(trans)
