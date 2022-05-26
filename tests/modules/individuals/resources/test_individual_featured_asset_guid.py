# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

from tests import utils
from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.asset_groups.resources import utils as asset_group_utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('individuals', 'sightings'), reason='Individuals module disabled'
)
def test_patch_featured_asset_guid_on_individual(
    db, flask_app_client, researcher_1, request, test_root
):

    # this test is a monster because it involves almost all of the major modules
    from app.modules.encounters.models import Encounter
    from app.modules.sightings.models import Sighting

    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root
    )

    assert len(uuids['encounters']) == 1
    encounter_uuid = uuids['encounters'][0]

    enc = Encounter.query.get(encounter_uuid)

    with db.session.begin():
        db.session.add(enc)

    sighting_uuid = uuids['sighting']
    sighting = Sighting.query.get(sighting_uuid)
    assert sighting is not None

    new_asset_group = utils.generate_asset_group_instance(researcher_1)

    with db.session.begin():
        db.session.add(new_asset_group)

    new_asset_1 = utils.generate_asset_instance(new_asset_group.guid)
    new_asset_2 = utils.generate_asset_instance(new_asset_group.guid)

    with db.session.begin():
        db.session.add(new_asset_group)
        db.session.add(new_asset_1)
        db.session.add(new_asset_2)

    sighting.add_asset(new_asset_1)

    individual_response = individual_utils.create_individual(
        flask_app_client, researcher_1, 200, {'encounters': [{'id': str(enc.guid)}]}
    )

    from app.modules.individuals.models import Individual

    individual = Individual.query.get(individual_response.json['guid'])

    assert individual is not None
    assert new_asset_1.guid is not None
    assert new_asset_2.guid is not None

    ann_1 = None
    ann_2 = None

    try:
        ann_resp_1 = annot_utils.create_annotation(
            flask_app_client,
            researcher_1,
            str(new_asset_1.guid),
            str(enc.guid),
        )
        ann_guid_1 = ann_resp_1.json['guid']

        from app.modules.annotations.models import Annotation

        ann_1 = Annotation.query.get(ann_guid_1)

        assert enc.guid == individual.encounters[0].guid
        assert len(enc.annotations) == 1
        assert individual.get_featured_asset_guid() == new_asset_1.guid

        ann_resp_2 = annot_utils.create_annotation(
            flask_app_client,
            researcher_1,
            str(new_asset_2.guid),
            str(enc.guid),
        )
        ann_guid_2 = ann_resp_2.json['guid']
        ann_2 = Annotation.query.get(ann_guid_2)

        assert len(enc.annotations) == 2

        sighting.add_asset(new_asset_2)

        individual.set_featured_asset_guid(new_asset_2.guid)

        assert individual.get_featured_asset_guid() == new_asset_2.guid

        # ok now the API
        patch_op = [
            utils.patch_replace_op('featuredAssetGuid', '%s' % new_asset_1.guid),
        ]

        individual_utils.patch_individual(
            flask_app_client, researcher_1, '%s' % individual.guid, patch_op
        )

        assert individual.get_featured_asset_guid() == new_asset_1.guid

        # The Asset was created by a hanging sighting, not part of an asset group, this will fail as that's not
        # how assets should be created
        individual_utils.read_individual_path(
            flask_app_client, researcher_1, f'{individual.guid}/featured_image', 400
        )

    finally:
        from app.extensions.git_store.tasks import delete_remote

        individual_utils.delete_individual(
            flask_app_client, researcher_1, str(individual.guid)
        )
        sighting.delete_cascade()
        if ann_1:
            ann_1.delete()
        if ann_2:
            ann_2.delete()
        delete_remote(str(new_asset_group.guid))
        asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, new_asset_group.guid
        )


@pytest.mark.skipif(
    module_unavailable('individuals', 'sightings'), reason='Individuals module disabled'
)
def test_featured_individual_read(db, flask_app_client, researcher_1, test_root, request):
    from app.modules.annotations.models import Annotation
    from app.modules.assets.models import Asset
    from app.modules.individuals.models import Individual

    # Specifically use the large one as we want multiple assets
    uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        large=True,
    )
    individual_guid = uuids['individual']
    enc_guids = uuids['encounters']
    asset_guids = uuids['assets']

    individual = Individual.query.get(individual_guid)
    assert individual
    asset0 = Asset.query.get(asset_guids[0])
    assert asset0
    asset1 = Asset.query.get(asset_guids[1])
    assert asset1

    # Before individual has any annotations, no assets are available
    image_response = individual_utils.read_individual_path(
        flask_app_client, researcher_1, f'{individual_guid}/featured_image'
    )
    assert image_response.content_type == 'image/jpeg'
    assert image_response.calculate_content_length() == 0
    image_response.close()

    ann0_resp = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        asset_guids[0],
        enc_guids[0],
    )
    ann0_guid = ann0_resp.json['guid']
    ann0 = Annotation.query.get(ann0_guid)
    request.addfinalizer(lambda: ann0.delete())

    # Now the featured asset guid should be the only one
    image_response = individual_utils.read_individual_path(
        flask_app_client, researcher_1, f'{individual_guid}/featured_image'
    )
    assert image_response.content_type == 'image/jpeg'
    asset_group_utils.validate_file_data(test_root, image_response.data, asset0.filename)
    image_response.close()

    # Add a second annotation
    ann1_resp = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        asset_guids[1],
        enc_guids[0],
    )
    ann1_guid = ann1_resp.json['guid']
    ann1 = Annotation.query.get(ann1_guid)
    request.addfinalizer(lambda: ann1.delete())

    # Make that asset the featured one
    db.session.refresh(individual)
    individual.set_featured_asset_guid(asset_guids[1])

    # Reread the path, should now be asset 1
    image_response = individual_utils.read_individual_path(
        flask_app_client, researcher_1, f'{individual_guid}/featured_image'
    )
    assert image_response.content_type == 'image/jpeg'
    asset_group_utils.validate_file_data(test_root, image_response.data, asset1.filename)
    image_response.close()
