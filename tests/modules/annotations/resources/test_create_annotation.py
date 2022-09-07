# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

import pytest

from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.asset_groups.resources import utils as ag_utils
from tests.modules.assets.resources import utils as asset_utils
from tests.modules.encounters.resources import utils as enc_utils
from tests.utils import module_unavailable


def test_get_annotation_not_found(flask_app_client):
    response = flask_app_client.get('/api/v1/annotations/wrong-uuid')
    assert response.status_code == 404
    response.close()


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_failures(flask_app_client, researcher_1, db, request, test_root):
    uuids = ag_utils.create_simple_asset_group_uuids(
        flask_app_client, researcher_1, request, test_root
    )
    asset_guid = uuids['assets'][0]

    # invalid ia_class
    response = annot_utils.create_annotation_simple(
        flask_app_client,
        researcher_1,
        asset_guid,
        ia_class=None,
        expected_status_code=422,
    )
    assert 'ia_class' in response.json['messages']

    # invalid bounds
    response = annot_utils.create_annotation_simple(
        flask_app_client,
        researcher_1,
        asset_guid,
        bounds={'rect': [0, 1, 2, 3, 4, 5]},
        expected_status_code=422,
    )
    assert response.json['message'] == 'bounds value is invalid'


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_and_delete_annotation(flask_app_client, researcher_1, request, test_root):
    # pylint: disable=invalid-name
    from app.modules.annotations.models import Annotation

    uuids = enc_utils.create_encounter(flask_app_client, researcher_1, request, test_root)
    enc_guid = uuids['encounters'][0]
    asset_guid = uuids['assets'][0]
    response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        asset_guid,
        enc_guid,
    )

    annotation_guid = response.json['guid']
    read_annotation = Annotation.query.get(response.json['guid'])
    assert read_annotation.asset_guid == uuid.UUID(asset_guid)

    # Try reading it back
    annot_utils.read_annotation(flask_app_client, researcher_1, annotation_guid)

    # make sure annot shows up on asset
    asset_res = asset_utils.read_asset(flask_app_client, researcher_1, asset_guid)
    assert annotation_guid in [annot['guid'] for annot in asset_res.json['annotations']]
    assert asset_res.json['annotations'][0]['bounds']['rect'] == [0, 1, 2, 3]

    # some misc tests
    assert not read_annotation.get_taxonomy_guid()
    assert read_annotation.get_owner_guid_str() == str(researcher_1.guid)
    assert read_annotation.get_sighting_guid_str() == uuids['sighting']

    # And deleting it
    annot_utils.delete_annotation(flask_app_client, researcher_1, annotation_guid)

    read_annotation = Annotation.query.get(annotation_guid)
    assert read_annotation is None


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_annotation_permission(
    flask_app_client,
    admin_user,
    staff_user,
    researcher_1,
    researcher_2,
    request,
    test_root,
):
    # Before we create any Annotations, find out how many are there already
    previous_annots = annot_utils.read_all_annotations(flask_app_client, staff_user)

    uuids = enc_utils.create_encounter(flask_app_client, researcher_1, request, test_root)
    enc_guid = uuids['encounters'][0]
    response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        uuids['assets'][0],
        enc_guid,
    )

    annotation_guid = response.json['guid']

    # staff user should be able to read anything
    annot_utils.read_annotation(flask_app_client, staff_user, annotation_guid)
    annot_utils.read_all_annotations(flask_app_client, staff_user)

    # admin user should not be able to read any annotations
    annot_utils.read_annotation(flask_app_client, admin_user, annotation_guid, 403)
    annot_utils.read_all_annotations(
        flask_app_client, admin_user, expected_status_code=403
    )

    # user that created annotation can read it back plus the list
    annot_utils.read_annotation(flask_app_client, researcher_1, annotation_guid)
    annots = annot_utils.read_all_annotations(flask_app_client, researcher_1)

    # due to the way the tests are run, there may be annotations left lying about,
    # don't rely on there only being one
    assert len(annots.json) == len(previous_annots.json) + 1
    annotation_present = False
    for annotation in annots.json:
        if annotation['guid'] == annotation_guid:
            annotation_present = True
        break
    assert annotation_present

    # but a different researcher can read the list but not the annotation
    annot_utils.read_annotation(flask_app_client, researcher_2, annotation_guid, 403)
    annot_utils.read_all_annotations(flask_app_client, researcher_2)


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_annotation_no_ags(
    flask_app_client, researcher_1, test_clone_asset_group_data, db, request
):
    # pylint: disable=invalid-name

    clone = ag_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )
    request.addfinalizer(lambda: clone.cleanup())

    response = annot_utils.create_annotation_simple(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_uuids'][0],
        expected_status_code=400,
    )
    assert (
        response.json['message']
        == 'cannot create encounter-less annotation on asset that does not have an asset group sighting'
    )
    clone.cleanup()


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_annotation_stage(flask_app_client, researcher_1, db, request, test_root):
    from app.modules.asset_groups.models import (
        AssetGroupSighting,
        AssetGroupSightingStage,
    )

    # pylint: disable=invalid-name
    (
        asset_group_uuid,
        asset_group_sighting_guid,
        asset_uuid,
    ) = ag_utils.create_simple_asset_group(
        flask_app_client, researcher_1, request, test_root
    )

    # manually check that the stage checking works by setting it to an incorrect value
    ags = AssetGroupSighting.query.get(asset_group_sighting_guid)
    ags.stage = AssetGroupSightingStage.detection
    response = annot_utils.create_annotation_simple(
        flask_app_client, researcher_1, asset_uuid, expected_status_code=400
    )
    assert (
        response.json['message']
        == 'cannot create encounter-less annotation on asset in asset group sighting that is not curating'
    )
    ags.stage = AssetGroupSightingStage.curation

    # Should now work
    annot_utils.create_annotation_simple(
        flask_app_client,
        researcher_1,
        asset_uuid,
    )


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_annotation_debug(
    flask_app_client, researcher_1, staff_user, db, request, test_root
):
    from tests import utils as test_utils

    # pylint: disable=invalid-name
    (
        asset_group_uuid,
        asset_group_sighting_guid,
        asset_uuid,
    ) = ag_utils.create_simple_asset_group(
        flask_app_client, researcher_1, request, test_root
    )
    annot_resp = annot_utils.create_annotation_simple(
        flask_app_client,
        researcher_1,
        asset_uuid,
    ).json

    annot_guid = annot_resp['guid']
    annot_debug = annot_utils.read_annotation(
        flask_app_client,
        staff_user,
        f'debug/{annot_guid}',
        expected_keys={'annotation', 'possible_asset_group_sightings'},
    ).json
    assert annot_debug['annotation']['asset_guid'] == annot_resp['asset_guid']
    assert len(annot_debug['possible_asset_group_sightings']) == 1
    debug_ags = annot_debug['possible_asset_group_sightings'][0]
    assert debug_ags['guid'] == asset_group_sighting_guid
    assert debug_ags['asset_group_guid'] == asset_group_uuid

    # Patch it in
    group_sighting = ag_utils.read_asset_group_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid
    )
    encounter_guid = group_sighting.json['config']['sighting']['encounters'][0]['guid']

    patch_data = [test_utils.patch_add_op('annotations', [annot_guid])]
    ag_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        f'{asset_group_sighting_guid}/encounter/{encounter_guid}',
        patch_data,
    )
    # Should now be the actual asset group sighting, not possibles
    annot_debug = annot_utils.read_annotation(
        flask_app_client,
        staff_user,
        f'debug/{annot_guid}',
        expected_keys={'annotation', 'asset_group_sighting'},
    ).json
    debug_ags = annot_debug['asset_group_sighting']
    assert debug_ags['guid'] == asset_group_sighting_guid
    assert debug_ags['asset_group_guid'] == asset_group_uuid

    commit_response = ag_utils.commit_asset_group_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid
    )
    sighting_uuid = commit_response.json['guid']
    # Should now be the actual asset group sighting, not possibles
    annot_debug = annot_utils.read_annotation(
        flask_app_client,
        staff_user,
        f'debug/{annot_guid}',
        expected_keys={'annotation', 'sighting'},
    ).json
    assert annot_debug['sighting']['guid'] == sighting_uuid
