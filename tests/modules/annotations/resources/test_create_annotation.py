# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.annotations.resources import utils as annot_utils


def test_create_and_delete_annotation(flask_app_client, researcher_1):
    # pylint: disable=invalid-name
    from app.modules.annotations.models import Annotation

    response = annot_utils.create_annotation(
        flask_app_client, researcher_1, 'This is a test annotation, please ignore'
    )

    annotation_guid = response.json['guid']
    read_annotation = Annotation.query.get(response.json['guid'])
    assert read_annotation.title == 'This is a test annotation, please ignore'
    assert read_annotation.owner == researcher_1

    # Try reading it back
    annot_utils.read_annotation(flask_app_client, researcher_1, annotation_guid)

    # And deleting it
    annot_utils.delete_annotation(flask_app_client, researcher_1, annotation_guid)

    read_annotation = Annotation.query.get(annotation_guid)
    assert read_annotation is None


def test_annotation_permission(
    flask_app_client, admin_user, staff_user, researcher_1, researcher_2
):
    # Before we create any Projects, find out how many are there already
    previous_list = annot_utils.read_all_annotations(flask_app_client, staff_user)

    response = annot_utils.create_annotation(
        flask_app_client, researcher_1, 'This is a test annotation, please ignore'
    )

    annotation_guid = response.json['guid']

    # staff user should be able to read anything
    annot_utils.read_annotation(flask_app_client, staff_user, annotation_guid)
    annot_utils.read_all_annotations(flask_app_client, staff_user)

    # admin user should not be able to read any annotations
    annot_utils.read_annotation(flask_app_client, admin_user, annotation_guid, 403)
    annot_utils.read_all_annotations(flask_app_client, admin_user, 403)

    # user that created annotation can read it back plus the list
    annot_utils.read_annotation(flask_app_client, researcher_1, annotation_guid)
    list_response = annot_utils.read_all_annotations(flask_app_client, researcher_1)

    # due to the way the tests are run, there may be annotations left lying about,
    # don't rely on there only being one
    assert len(list_response.json) == len(previous_list.json) + 1
    annotation_present = False
    for annotation in list_response.json:
        if annotation['guid'] == annotation_guid:
            annotation_present = True
            break
    assert annotation_present

    # but a different researcher can read the list but not the annotation
    annot_utils.read_annotation(flask_app_client, researcher_2, annotation_guid, 403)
    annot_utils.read_all_annotations(flask_app_client, researcher_2)

    # delete it
    annot_utils.delete_annotation(flask_app_client, researcher_1, annotation_guid)
