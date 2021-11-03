# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.asset_groups.resources import utils as asset_group_utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.annotations.resources import utils as annot_utils
from tests import utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('individuals', 'sightings'), reason='Individuals module disabled'
)
def test_patch_featured_asset_guid_on_individual(db, flask_app_client, researcher_1):

    # this test is a monster because it involves almost all of the major modules

    from app.modules.sightings.models import Sighting

    data_in = {
        'encounters': [{}],
        'startTime': '2000-01-01T01:01:01Z',
        'locationId': 'test',
    }

    response = sighting_utils.create_sighting(flask_app_client, researcher_1, data_in)

    from app.modules.encounters.models import Encounter

    response_json = response.json

    assert response_json['result']['encounters']
    assert response_json['result']['encounters'][0]
    assert response_json['result']['encounters'][0]['id']

    guid = response_json['result']['encounters'][0]['id']

    enc = Encounter.query.get(guid)
    assert enc is not None

    with db.session.begin():
        db.session.add(enc)

    sighting_id = response_json['result']['id']
    sighting = Sighting.query.get(sighting_id)
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

    individual = Individual.query.get(individual_response.json['result']['id'])

    assert individual is not None
    assert new_asset_1.guid is not None
    assert new_asset_2.guid is not None

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

    finally:
        from app.modules.asset_groups.tasks import delete_remote

        individual_utils.delete_individual(
            flask_app_client, researcher_1, str(individual.guid)
        )
        sighting.delete_cascade()
        ann_1.delete()
        ann_2.delete()
        delete_remote(str(new_asset_group.guid))
        asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, new_asset_group.guid
        )
