# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

import uuid
from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.submissions.resources import utils as sub_utils


def test_create_and_delete_annotation(
    flask_app_client, admin_user, researcher_1, test_clone_submission_data
):
    # pylint: disable=invalid-name
    from app.modules.annotations.models import Annotation

    clone = sub_utils.clone_submission(
        flask_app_client,
        admin_user,
        researcher_1,
        test_clone_submission_data['submission_uuid'],
        later_usage=True,
    )
    try:
        response = annot_utils.create_annotation(
            flask_app_client, researcher_1, test_clone_submission_data['asset_uuids'][0]
        )

        annotation_guid = response.json['guid']
        read_annotation = Annotation.query.get(response.json['guid'])
        assert read_annotation.asset_guid == uuid.UUID(
            test_clone_submission_data['asset_uuids'][0]
        )

        # Try reading it back
        annot_utils.read_annotation(flask_app_client, researcher_1, annotation_guid)

        # And deleting it
        annot_utils.delete_annotation(flask_app_client, researcher_1, annotation_guid)

        read_annotation = Annotation.query.get(annotation_guid)
        assert read_annotation is None
    except Exception as ex:
        raise ex
    finally:
        clone.cleanup()


# TODO doesn't work at the moment
def test_annotation_permission(
    flask_app_client,
    admin_user,
    staff_user,
    researcher_1,
    researcher_2,
    test_clone_submission_data,
):
    # Before we create any Annotations, find out how many are there already
    previous_wbia_annots = annot_utils.read_all_annotations(flask_app_client, staff_user)
    previous_local_annots = annot_utils.read_all_annotations(
        flask_app_client, staff_user, local_only=True
    )
    clone = sub_utils.clone_submission(
        flask_app_client,
        admin_user,
        researcher_1,
        test_clone_submission_data['submission_uuid'],
        later_usage=True,
    )
    try:
        response = annot_utils.create_annotation(
            flask_app_client, researcher_1, test_clone_submission_data['asset_uuids'][0]
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
        wbia_annots = annot_utils.read_all_annotations(flask_app_client, researcher_1)
        local_annots = annot_utils.read_all_annotations(
            flask_app_client, researcher_1, local_only=True
        )

        # due to the way the tests are run, there may be annotations left lying about,
        # don't rely on there only being one
        assert wbia_annots.json == previous_wbia_annots.json
        assert len(local_annots.json) == len(previous_local_annots.json) + 1
        annotation_present = False
        for annotation in local_annots.json:
            if annotation['guid'] == annotation_guid:
                annotation_present = True
            break
        assert annotation_present

        # but a different researcher can read the list but not the annotation
        annot_utils.read_annotation(flask_app_client, researcher_2, annotation_guid, 403)
        annot_utils.read_all_annotations(flask_app_client, researcher_2)

        # delete it
        annot_utils.delete_annotation(flask_app_client, researcher_1, annotation_guid)

    except Exception as ex:
        raise ex
    finally:
        clone.cleanup()
