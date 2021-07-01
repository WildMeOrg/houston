# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

import uuid
from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.asset_groups.resources import utils as sub_utils
from tests.modules.encounters.resources import utils as enc_utils
from tests.modules.assets.resources import utils as asset_utils


def test_get_annotation_not_found(flask_app_client):
    response = flask_app_client.get('/api/v1/annotations/wrong-uuid')
    assert response.status_code == 404


def test_create_failures(flask_app_client, researcher_1, test_clone_asset_group_data, db):
    # pylint: disable=invalid-name
    # from app.modules.annotations.models import Annotation

    sub_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )

    # invalid ia_class
    response = annot_utils.create_annotation_simple(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_uuids'][0],
        ia_class=None,
        expected_status_code=422,
    )
    assert 'ia_class' in response.json['messages']

    # invalid bounds
    response = annot_utils.create_annotation_simple(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_uuids'][0],
        bounds={'rect': [0, 1, 2, 3, 4, 5]},
        expected_status_code=422,
    )
    assert response.json['message'] == 'bounds value is invalid'


def test_create_and_delete_annotation(
    flask_app_client, researcher_1, test_clone_asset_group_data
):
    # pylint: disable=invalid-name
    from app.modules.annotations.models import Annotation

    sub_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )
    asset_guid = test_clone_asset_group_data['asset_uuids'][0]

    response = enc_utils.create_encounter(flask_app_client, researcher_1)
    enc_guid = response.json['result']['encounters'][0]['id']
    response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        asset_guid,
        enc_guid,
    )

    annotation_guid = response.json['guid']
    read_annotation = Annotation.query.get(response.json['guid'])
    assert read_annotation.asset_guid == uuid.UUID(
        test_clone_asset_group_data['asset_uuids'][0]
    )

    # Try reading it back
    annot_utils.read_annotation(flask_app_client, researcher_1, annotation_guid)

    # make sure annot shows up on asset
    asset_res = asset_utils.read_asset(flask_app_client, researcher_1, asset_guid)
    assert len(asset_res.json['annotations']) == 1

    # And deleting it
    annot_utils.delete_annotation(flask_app_client, researcher_1, annotation_guid)

    read_annotation = Annotation.query.get(annotation_guid)
    assert read_annotation is None


def test_annotation_permission(
    flask_app_client,
    admin_user,
    staff_user,
    researcher_1,
    researcher_2,
    test_clone_asset_group_data,
):
    # Before we create any Annotations, find out how many are there already
    previous_annots = annot_utils.read_all_annotations(flask_app_client, staff_user)
    sub_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )

    response = enc_utils.create_encounter(flask_app_client, researcher_1)
    enc_guid = response.json['result']['encounters'][0]['id']
    response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_uuids'][0],
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

    # delete it
    annot_utils.delete_annotation(flask_app_client, researcher_1, annotation_guid)
