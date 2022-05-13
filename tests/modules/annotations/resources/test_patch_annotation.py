# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.sightings.resources import utils as sighting_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_patch_annotation(
    flask_app_client,
    admin_user,
    researcher_1,
    request,
    test_root,
):
    # pylint: disable=invalid-name
    from app.modules.annotations.models import Annotation
    from app.modules.encounters.models import Encounter

    # Encounter create creates the sighting and assets
    large_sighting_uuids = sighting_utils.create_large_sighting(
        flask_app_client, researcher_1, request, test_root
    )
    sighting_1_enc_guid_1 = large_sighting_uuids['encounters'][0]

    annot_response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        large_sighting_uuids['assets'][0],
        sighting_1_enc_guid_1,
    ).json

    annotation_guid = annot_response['guid']
    read_annotation = Annotation.query.get(annotation_guid)
    assert read_annotation.asset_guid == uuid.UUID(large_sighting_uuids['assets'][0])
    first_encounter = Encounter.query.get(sighting_1_enc_guid_1)
    assert len(first_encounter.annotations) == 1
    assert first_encounter.annotations[0].guid == uuid.UUID(annotation_guid)

    basic_sighting_uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root
    )
    sighting_2_enc_guid = basic_sighting_uuids['encounters'][0]

    # Try changing to encounter on different sighting, should be rejected
    annot_utils.patch_annotation(
        flask_app_client,
        annotation_guid,
        researcher_1,
        [{'op': 'replace', 'path': '/encounter_guid', 'value': sighting_2_enc_guid}],
        409,
    )
    sighting_1_enc_guid_2 = large_sighting_uuids['encounters'][1]
    # Try changing to encounter on same sighting, should succeed
    annot_utils.patch_annotation(
        flask_app_client,
        annotation_guid,
        researcher_1,
        [{'op': 'replace', 'path': '/encounter_guid', 'value': sighting_1_enc_guid_2}],
    )
    second_encounter = Encounter.query.get(sighting_1_enc_guid_2)
    assert len(first_encounter.annotations) == 0
    assert len(second_encounter.annotations) == 1
    assert second_encounter.annotations[0].guid == uuid.UUID(annotation_guid)

    # And deleting it
    annot_utils.delete_annotation(flask_app_client, researcher_1, annotation_guid)

    read_annotation = Annotation.query.get(annotation_guid)
    assert read_annotation is None
