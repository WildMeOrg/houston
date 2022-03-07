# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import logging

import uuid
import datetime

from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.annotations.resources import utils as annot_utils

from tests import utils
import pytest

from tests.utils import module_unavailable


log = logging.getLogger(__name__)


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_get_individual_not_found(flask_app_client, researcher_1):
    response = individual_utils.read_individual(
        flask_app_client, researcher_1, uuid.uuid4, expected_status_code=404
    )
    assert response.status_code == 404
    response.close()


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_create_read_delete_individual(db, flask_app_client):
    from app.modules.individuals.models import Individual

    temp_owner = utils.generate_user_instance(
        email='owner@localhost',
        is_researcher=True,
    )
    temp_enc = utils.generate_encounter_instance(
        user_email='enc@user', user_password='encuser', user_full_name='enc user 1'
    )
    encounter_json = {'encounters': [{'id': str(temp_enc.guid)}]}
    temp_enc.owner = temp_owner
    response = individual_utils.create_individual(
        flask_app_client, temp_owner, expected_status_code=200, data_in=encounter_json
    )
    individual_guid = response.json['result']['id']

    assert individual_guid is not None

    read_individual = Individual.query.get(individual_guid)
    assert read_individual is not None

    individual_utils.delete_individual(flask_app_client, temp_owner, individual_guid)
    read_individual = Individual.query.get(individual_guid)
    assert read_individual is None

    response = individual_utils.read_individual(
        flask_app_client, temp_owner, individual_guid, expected_status_code=404
    )
    assert response.status_code == 404

    with db.session.begin():
        db.session.delete(temp_owner)
        db.session.delete(temp_enc)


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_read_encounter_from_edm(db, flask_app_client):
    from app.modules.individuals.models import Individual

    temp_owner = utils.generate_user_instance(
        email='owner@localhost',
        is_researcher=True,
    )
    temp_enc = utils.generate_encounter_instance(
        user_email='enc@user', user_password='encuser', user_full_name='enc user 1'
    )
    encounter_json = {'encounters': [{'id': str(temp_enc.guid)}]}
    temp_enc.owner = temp_owner
    response = individual_utils.create_individual(
        flask_app_client, temp_owner, expected_status_code=200, data_in=encounter_json
    )

    individual_guid = response.json['result']['id']

    read_response = individual_utils.read_individual(
        flask_app_client, temp_owner, individual_guid, expected_status_code=200
    )

    read_guid = read_response.json['id']
    assert read_guid is not None

    read_individual = Individual.query.get(read_guid)

    assert read_individual is not None

    individual_utils.delete_individual(flask_app_client, temp_owner, individual_guid)
    read_individual = Individual.query.get(individual_guid)

    assert read_individual is None

    with db.session.begin():
        db.session.delete(temp_owner)
        db.session.delete(temp_enc)


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_add_remove_encounters(db, flask_app_client, researcher_1, request, test_root):
    from app.modules.individuals.models import Individual
    from app.modules.encounters.models import Encounter
    from app.modules.sightings.models import Sighting

    data_in = {
        'time': datetime.datetime.now().isoformat() + '+00:00',
        'timeSpecificity': 'time',
        'context': 'test',
        'locationId': 'test',
        'encounters': [
            {},
            {},
            {},
            {},
            {'locationId': 'Monster Island'},
        ],
    }

    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, data_in
    )

    sighting_id = uuids['sighting']
    sighting = Sighting.query.get(sighting_id)
    assert len(uuids['encounters']) == 5

    enc_1 = Encounter(
        guid=uuids['encounters'][0],
        owner_guid=researcher_1.guid,
    )

    enc_2 = Encounter(
        guid=uuids['encounters'][1],
        owner_guid=researcher_1.guid,
    )

    enc_3 = Encounter(
        guid=uuids['encounters'][2],
        owner_guid=researcher_1.guid,
    )

    enc_4 = Encounter(
        guid=uuids['encounters'][3],
        owner_guid=researcher_1.guid,
    )

    response = individual_utils.create_individual(
        flask_app_client, researcher_1, 200, {'encounters': [{'id': str(enc_1.guid)}]}
    )
    individual_1 = Individual.query.get(response.json['result']['id'])

    # # let's start with one
    # individual_1.add_encounter(enc_1)

    assert str(enc_1.guid) in [
        str(encounter.guid) for encounter in individual_1.get_encounters()
    ]

    add_encounters = [
        utils.patch_add_op('encounters', [str(enc_2.guid)]),
    ]

    individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        '%s' % individual_1.guid,
        patch_data=add_encounters,
        headers=None,
        expected_status_code=200,
    )

    assert str(enc_2.guid) in [
        str(encounter.guid) for encounter in individual_1.get_encounters()
    ]

    # remove the one we just verified was there
    remove_encounters = [
        utils.patch_remove_op('encounters', str(enc_1.guid)),
    ]

    individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        '%s' % individual_1.guid,
        remove_encounters,
        None,
        200,
    )

    assert str(enc_1.guid) not in [
        str(encounter.guid) for encounter in individual_1.get_encounters()
    ]

    # okay, now with multiple
    add_encounters = [
        utils.patch_add_op('encounters', [str(enc_3.guid), str(enc_4.guid)]),
    ]

    individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        '%s' % individual_1.guid,
        add_encounters,
        None,
        200,
    )

    assert str(enc_3.guid), str(enc_4.guid) in [
        str(encounter.guid) for encounter in individual_1.get_encounters()
    ]

    # removing all encounters will trigger delete cascade and clean up EDM
    # hack because sighting patch only takes one ID for remove. another PR for another day.
    enc_guids = [str(enc_2.guid), str(enc_3.guid), str(enc_4.guid)]

    for enc_guid in enc_guids:
        sighting_utils.patch_sighting(
            flask_app_client,
            researcher_1,
            sighting_id,
            patch_data=[
                {'op': 'remove', 'path': '/encounters', 'value': enc_guid},
            ],
            headers=(
                ('x-allow-delete-cascade-sighting', True),
                ('x-allow-delete-cascade-individual', True),
            ),
        )

    individual_1.delete()
    sighting.delete_cascade()


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_individual_has_detailed_encounter_from_edm(
    db,
    flask_app_client,
    researcher_1,
    request,
    test_root,
    test_asset_group_uuid,
):
    from app.modules.encounters.models import Encounter
    from app.modules.sightings.models import Sighting
    from app.modules.asset_groups.models import AssetGroup

    data_in = {
        'encounters': [
            {
                'decimalLatitude': 25.9999,
                'decimalLongitude': 25.9999,
                'verbatimLocality': 'Antarctica',
                'locationId': 'Antarctica',
                'time': '2010-01-01T01:01:01+00:00',
                'timeSpecificity': 'time',
            }
        ],
        'time': '2000-01-01T01:01:01+00:00',
        'timeSpecificity': 'time',
        'locationId': 'test',
    }

    individual_id = None
    enc = None

    try:
        uuids = sighting_utils.create_sighting(
            flask_app_client, researcher_1, request, test_root, data_in
        )

        assert len(uuids['encounters']) == 1
        encounter_uuid = uuids['encounters'][0]
        assets = AssetGroup.query.get(test_asset_group_uuid).assets
        enc = Encounter.query.get(encounter_uuid)
        enc.sighting.add_assets(assets)
        for asset in assets:
            annot_utils.create_annotation(
                flask_app_client, researcher_1, str(asset.guid), str(enc.guid)
            )

        with db.session.begin():
            db.session.add(enc)

        sighting_uuid = uuids['sighting']
        sighting = Sighting.query.get(sighting_uuid)
        assert sighting is not None

        encounter = Encounter.query.get(enc.guid)
        encounter.asset_group_sighting_encounter_guid = uuid.uuid4()

        individual_data_in = {
            'names': [{'context': 'defaultName', 'value': 'Wilbur'}],
            'encounters': [{'id': str(enc.guid)}],
        }

        individual_response = individual_utils.create_individual(
            flask_app_client, researcher_1, 200, individual_data_in
        )

        assert individual_response.json['result']['id'] is not None

        individual_id = individual_response.json['result']['id']

        individual_json = individual_utils.read_individual(
            flask_app_client, researcher_1, individual_id
        ).json

        enc_json = individual_json['encounters'][0]
        assert enc_json['decimalLatitude'] == '25.9999'
        assert enc_json['decimalLongitude'] == '25.9999'
        assert enc_json['verbatimLocality'] == 'Antarctica'
        assert enc_json['locationId'] == 'Antarctica'
        assert enc_json['time'] == '2010-01-01T01:01:01+00:00'
        assert enc_json['annotations']
        assert enc_json['annotations'][0]['asset_src']

    finally:
        individual_utils.delete_individual(flask_app_client, researcher_1, individual_id)
        if enc:
            enc.delete_cascade()


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_individual_mixed_edm_houston_patch(
    db, flask_app_client, researcher_1, request, test_root
):
    uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )
    individual_id = uuids['individual']
    valid_names_data_A = {'context': 'A', 'value': 'value-A'}

    edm_patch_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        [
            {'op': 'replace', 'path': '/timeOfBirth', 'value': '1445410800000'},
            {'op': 'replace', 'path': '/timeOfDeath', 'value': 'cedric'},
        ],
        expected_status_code=500,
    )

    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json
    assert (
        'due to an invalid String cedric for Long conversion'
        in edm_patch_response.json['message']
    )
    assert individual_json['timeOfBirth'] == '0'

    patch_individual_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        [
            {'op': 'add', 'path': '/featuredAssetGuid', 'value': str(uuid.uuid4())},
            {'op': 'add', 'path': '/names', 'value': valid_names_data_A},
        ],
        expected_status_code=409,
    )

    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json
    assert (
        "'featuredAssetGuid')]) could not succeed."
        in patch_individual_response.json['message']
    )
    assert individual_json['featuredAssetGuid'] is None

    # Houston and EDM patch together
    individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        [
            {'op': 'replace', 'path': '/timeOfBirth', 'value': '1445410800000'},
            {'op': 'add', 'path': '/names', 'value': valid_names_data_A},
            {'op': 'add', 'path': '/featuredAssetGuid', 'value': str(uuid.uuid4())},
        ],
        expected_status_code=417,
    )

    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json

    # EDM patch should have succeeded, Houston failed
    assert individual_json['timeOfBirth'] == '1445410800000'
    assert individual_json['names'] == []
