# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

import uuid
from tests import utils
from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.asset_groups.resources import utils as sub_utils
from tests.modules.encounters.resources import utils as enc_utils


def test_patch_annotation(
    flask_app_client, admin_user, researcher_1, test_clone_asset_group_data
):
    # pylint: disable=invalid-name
    from app.modules.annotations.models import Annotation
    from app.modules.encounters.models import Encounter

    sub_utils.clone_asset_group(
        flask_app_client,
        admin_user,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )

    response = enc_utils.create_encounter(flask_app_client, researcher_1)
    first_enc_guid = response.json['result']['guid']

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

    response = enc_utils.create_encounter(flask_app_client, researcher_1)
    second_enc_guid = response.json['result']['guid']
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

    # And deleting it
    annot_utils.delete_annotation(flask_app_client, researcher_1, annotation_guid)

    read_annotation = Annotation.query.get(annotation_guid)
    assert read_annotation is None
