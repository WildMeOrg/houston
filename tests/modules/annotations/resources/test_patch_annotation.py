# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

from tests import utils
from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.asset_groups.resources import utils as sub_utils
from tests.modules.encounters.resources import utils as enc_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_patch_annotation(
    flask_app_client,
    admin_user,
    researcher_1,
    test_clone_asset_group_data,
    request,
    test_root,
):
    # pylint: disable=invalid-name
    from app.modules.annotations.models import Annotation
    from app.modules.encounters.models import Encounter

    clone = sub_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )

    uuids = enc_utils.create_encounter(flask_app_client, researcher_1, request, test_root)
    first_enc_guid = uuids['encounters'][0]

    response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_uuids'][0],
        first_enc_guid,
    )

    annotation_guid = response.json['guid']
    read_annotation = Annotation.query.get(annotation_guid)
    assert read_annotation.asset_guid == uuid.UUID(
        test_clone_asset_group_data['asset_uuids'][0]
    )
    first_encounter = Encounter.query.get(first_enc_guid)
    assert len(first_encounter.annotations) == 1
    assert first_encounter.annotations[0].guid == uuid.UUID(annotation_guid)

    uuids = enc_utils.create_encounter(flask_app_client, researcher_1, request, test_root)
    second_enc_guid = uuids['encounters'][0]
    move_to_second_enc = [
        utils.patch_replace_op('encounter_guid', '%s' % second_enc_guid),
    ]

    # Try changing encounter
    annot_utils.patch_annotation(
        flask_app_client, annotation_guid, researcher_1, move_to_second_enc
    )

    second_encounter = Encounter.query.get(second_enc_guid)
    assert len(first_encounter.annotations) == 0
    assert len(second_encounter.annotations) == 1
    assert second_encounter.annotations[0].guid == uuid.UUID(annotation_guid)

    # change ia_class via patch
    assert read_annotation.ia_class == 'test'
    new_ia_class = 'test2'
    patch_arg = [
        utils.patch_replace_op('ia_class', new_ia_class),
    ]
    annot_utils.patch_annotation(
        flask_app_client, annotation_guid, researcher_1, patch_arg
    )
    read_annotation = Annotation.query.get(annotation_guid)
    assert read_annotation.ia_class == new_ia_class

    # fail setting ia_class null
    patch_arg = [
        utils.patch_replace_op('ia_class', None),
    ]
    annot_utils.patch_annotation(
        flask_app_client,
        annotation_guid,
        researcher_1,
        patch_arg,
        expected_status_code=422,
    )
    read_annotation = Annotation.query.get(annotation_guid)
    assert read_annotation.ia_class == new_ia_class  # unchanged from before

    # change bounds via patch
    new_bounds = {'rect': [100, 200, 300, 400]}
    patch_arg = [
        utils.patch_replace_op('bounds', new_bounds),
    ]
    annot_utils.patch_annotation(
        flask_app_client, annotation_guid, researcher_1, patch_arg
    )
    read_annotation = Annotation.query.get(annotation_guid)
    assert read_annotation.bounds == new_bounds

    # change bounds via patch, but invalid bounds value
    new_bounds = {'rect': [100, 200]}
    patch_arg = [
        utils.patch_replace_op('bounds', new_bounds),
    ]
    response = annot_utils.patch_annotation(
        flask_app_client,
        annotation_guid,
        researcher_1,
        patch_arg,
        expected_status_code=422,
    )
    assert response.json['message'] == 'bounds value is invalid'
    read_annotation = Annotation.query.get(annotation_guid)
    assert read_annotation.bounds != new_bounds

    # And deleting it
    annot_utils.delete_annotation(flask_app_client, researcher_1, annotation_guid)

    read_annotation = Annotation.query.get(annotation_guid)
    assert read_annotation is None

    clone.cleanup()
