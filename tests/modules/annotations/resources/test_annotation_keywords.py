# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

# import uuid
# from tests import utils
from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.asset_groups.resources import utils as sub_utils
from tests.modules.encounters.resources import utils as enc_utils


def test_keywords_on_annotation(
    flask_app_client, admin_user, researcher_1, test_clone_asset_group_data
):
    # pylint: disable=invalid-name
    from app.modules.annotations.models import Annotation
    from app.modules.keywords.models import Keyword

    # this gives us an "existing" keyword to work with
    keyword_value = 'TEST_VALUE_1'
    keyword = Keyword(value=keyword_value)
    assert keyword is not None

    sub_utils.clone_asset_group(
        flask_app_client,
        admin_user,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )

    # for now i guess we *must* have an encounter; but this likely will change
    response = enc_utils.create_encounter(flask_app_client, researcher_1)
    first_enc_guid = response.json['result']['guid']

    response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_uuids'][0],
        first_enc_guid,
    )

    annotation_guid = response.json['guid']
    annotation = Annotation.query.get(annotation_guid)
    assert annotation is not None

    return
    # annot_utils.patch_annotation(
    # flask_app_client, annotation_guid, researcher_1, move_to_second_enc
    # )

    # And deleting it
    annot_utils.delete_annotation(flask_app_client, researcher_1, annotation_guid)
    read_annotation = Annotation.query.get(annotation_guid)
    assert read_annotation is None
