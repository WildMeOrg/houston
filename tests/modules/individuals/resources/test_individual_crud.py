# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import logging
import uuid

import pytest

from tests import utils
from tests import utils as test_utils
from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.site_settings.resources import utils as setting_utils
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
    time_of_death = '2099-01-01T00:00:00+00:00'
    time_of_birth = '1999-02-02T00:01:00+00:00'
    sex = 'male'
    comments = 'some random text'
    individual_json = {
        'encounters': [{'id': str(temp_enc.guid)}],
        'names': [{'context': 'main', 'value': 'Cuthbert'}],
        'sex': sex,
        'comments': comments,
        'timeOfDeath': time_of_death,
        'timeOfBirth': time_of_birth,
    }
    temp_enc.owner = temp_owner
    response = individual_utils.create_individual(
        flask_app_client, temp_owner, expected_status_code=200, data_in=individual_json
    ).json
    individual_guid = response['guid']
    assert len(response['encounters']) == 1
    assert len(response['names']) == 1
    assert response['sex'] == sex
    assert response['comments'] == comments
    assert response['timeOfDeath'] == time_of_death
    assert response['timeOfBirth'] == time_of_birth

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
def test_read_encounter(db, flask_app_client):
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

    individual_guid = response.json['guid']

    read_response = individual_utils.read_individual(
        flask_app_client, temp_owner, individual_guid, expected_status_code=200
    )

    read_guid = read_response.json['guid']
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
    from app.modules.complex_date_time.models import Specificities
    from app.modules.encounters.models import Encounter
    from app.modules.individuals.models import Individual
    from app.modules.sightings.models import Sighting

    test_time = test_utils.isoformat_timestamp_now()
    data_in = {
        'time': test_time,
        'timeSpecificity': 'time',
        'locationId': test_utils.get_valid_location_id(),
        'encounters': [
            {},
            {},
            {},
            {},
            {'locationId': str(uuid.uuid4())},
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
    individual_1 = Individual.query.get(response.json['guid'])

    assert individual_1.get_last_seen_time_isoformat() == test_time
    assert individual_1.get_last_seen_time_specificity() == Specificities.time

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

    # Check individual encounters times (which are null and should
    # return the sighting time)
    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_1.guid
    ).json
    for encounter in individual_json['encounters']:
        assert encounter['timeSpecificity'] == 'time'
        assert encounter['time'] == test_time

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
def test_individual_has_detailed_encounter(
    db,
    flask_app_client,
    researcher_1,
    request,
    test_root,
    test_asset_group_uuid,
):
    from app.modules.asset_groups.models import AssetGroup
    from app.modules.encounters.models import Encounter
    from app.modules.sightings.models import Sighting

    loc_id = test_utils.get_valid_location_id()
    data_in = {
        'encounters': [
            {
                'decimalLatitude': 25.9999,
                'decimalLongitude': 25.9999,
                'verbatimLocality': 'Antarctica',
                'locationId': loc_id,
                'time': '2010-01-01T01:01:01+00:00',
                'timeSpecificity': 'time',
            }
        ],
        'time': '2000-01-01T01:01:01+00:00',
        'timeSpecificity': 'time',
        'locationId': loc_id,
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

        assert individual_response.json['guid'] is not None

        individual_id = individual_response.json['guid']

        individual_json = individual_utils.read_individual(
            flask_app_client, researcher_1, individual_id
        ).json

        enc_json = individual_json['encounters'][0]
        assert enc_json['decimalLatitude'] == 25.9999
        assert enc_json['decimalLongitude'] == 25.9999
        assert enc_json['verbatimLocality'] == 'Antarctica'
        assert enc_json['locationId'] == loc_id
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
def test_individual_patch_errors(db, flask_app_client, researcher_1, request, test_root):
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
            {
                'op': 'replace',
                'path': '/timeOfBirth',
                'value': '2000-01-02T03:04:05+00:00',
            },
            {'op': 'replace', 'path': '/timeOfDeath', 'value': 'cedric'},
        ],
        expected_status_code=409,
    )
    assert (
        '"cedric" is not a valid value for timeOfDeath'
        in edm_patch_response.json['message']
    )
    edm_patch_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        [
            {'op': 'replace', 'path': '/timeOfBirth', 'value': 'week last wednesday'},
        ],
        expected_status_code=409,
    )
    assert (
        '"week last wednesday" is not a valid value for timeOfBirth'
        in edm_patch_response.json['message']
    )
    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json

    assert not individual_json['timeOfBirth']
    assert not individual_json['timeOfDeath']

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
    new_sex = 'invalid value'
    patch_individual_response = individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        [
            {'op': 'add', 'path': '/sex', 'value': new_sex},
        ],
        expected_status_code=409,
    )
    assert (
        f'"{new_sex}" is not a valid value for sex'
        in patch_individual_response.json['message']
    )

    individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        [
            {
                'op': 'replace',
                'path': '/timeOfBirth',
                'value': '2000-01-02T03:04:05+00:00',
            },
            {'op': 'add', 'path': '/names', 'value': valid_names_data_A},
            {'op': 'add', 'path': '/featuredAssetGuid', 'value': str(uuid.uuid4())},
        ],
        expected_status_code=409,
    )

    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json

    # EDM patch should have succeeded, Houston failed
    #  no longer true:  edm is gone, so everything failed
    assert not individual_json['timeOfBirth']
    assert individual_json['names'] == []


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_individual_patch_add_remove(
    db, flask_app_client, researcher_1, request, test_root
):
    uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )
    individual_id = uuids['individual']
    time_of_death = '2099-01-01T00:00:00+00:00'
    time_of_birth = '1999-02-02T00:01:00+00:00'
    sex = 'female'
    comments = 'some random text'

    individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        [
            {'op': 'add', 'path': '/timeOfDeath', 'value': time_of_death},
            {'op': 'add', 'path': '/timeOfBirth', 'value': time_of_birth},
            {'op': 'add', 'path': '/sex', 'value': sex},
            {'op': 'add', 'path': '/comments', 'value': comments},
        ],
    )
    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json

    assert individual_json['timeOfDeath'] == time_of_death
    assert individual_json['timeOfBirth'] == time_of_birth
    assert individual_json['sex'] == sex
    assert individual_json['comments'] == comments

    individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        [
            {'op': 'remove', 'path': '/timeOfDeath'},
            {'op': 'remove', 'path': '/timeOfBirth'},
            {'op': 'remove', 'path': '/sex'},
            {'op': 'remove', 'path': '/comments'},
        ],
    )

    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json
    assert individual_json['timeOfDeath'] is None
    assert individual_json['timeOfBirth'] is None
    assert individual_json['sex'] is None
    assert individual_json['comments'] is None


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_custom_field_patch(
    db, flask_app_client, researcher_1, admin_user, request, test_root
):
    uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )
    individual_id = uuids['individual']

    custom_field_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'personality (test custom field)',
        cls='Individual',
    )
    assert custom_field_id is not None

    custom_field_val = 'magnanimous'
    custom_fields = {custom_field_id: custom_field_val}

    individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        individual_id,
        [{'op': 'replace', 'path': '/customFields', 'value': custom_fields}],
    )
    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_id
    ).json

    assert individual_json['customFields'] == custom_fields


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_patch_encounter(db, flask_app_client, researcher_1, request, test_root):

    from app.modules.individuals.models import Individual

    # this one just to init the individual
    temp_enc = utils.generate_encounter_instance(
        user_email='enc@user', user_password='encuser', user_full_name='enc user 1'
    )
    temp_enc.owner = researcher_1
    encounter_json = {'encounters': [{'id': str(temp_enc.guid)}]}
    ind_create_resp = individual_utils.create_individual(
        flask_app_client, researcher_1, expected_status_code=200, data_in=encounter_json
    )
    individual_guid = ind_create_resp.json['guid']

    sighting_data_in = {
        'time': test_utils.isoformat_timestamp_now(),
        'timeSpecificity': 'time',
        'locationId': test_utils.get_valid_location_id(),
        'encounters': [{}],
    }
    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, sighting_data_in
    )
    encounter_guid = uuids['encounters'][0]
    sighting_guid = uuids['sighting']

    add_enc_opp = [utils.patch_add_op('encounters', [encounter_guid])]
    individual_utils.patch_individual(
        flask_app_client,
        researcher_1,
        '%s' % individual_guid,
        patch_data=add_enc_opp,
        headers=None,
        expected_status_code=200,
    )

    individual_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individual_guid
    ).json
    # the individual's encounters (includes temp_enc and the patched enc)
    individual_enc_guids = {enc['guid'] for enc in individual_json['encounters']}
    assert encounter_guid in individual_enc_guids
    # the encounters' individuals
    enc_individual_guids = {
        enc['individual']['guid'] for enc in individual_json['encounters']
    }
    assert all([ind_guid == individual_guid for ind_guid in enc_individual_guids])

    sighting_json = sighting_utils.read_sighting(
        flask_app_client, researcher_1, sighting_guid
    ).json

    sighting_enc_ind_guid = sighting_json['encounters'][0]['individual']['guid']
    assert individual_guid == sighting_enc_ind_guid

    # other objs are cleaned-up automatically
    temp_enc.delete()
    individual = Individual.query.get(individual_guid)
    individual.delete()


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_create_with_public_encounters(
    db, flask_app_client, researcher_1, researcher_2, staff_user, request, test_root
):
    # pylint: disable=invalid-name
    import tests.modules.asset_groups.resources.utils as asset_group_utils

    uuids1 = sighting_utils.create_sighting(
        flask_app_client, None, request, test_root, commit_user=researcher_2
    )
    # calling code responsibility to clear up if public data
    request.addfinalizer(
        lambda: asset_group_utils.delete_asset_group(
            flask_app_client, staff_user, uuids1['asset_group']
        )
    )
    uuids2 = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, commit_user=researcher_1
    )
    ind_data = {
        'encounters': [{'id': uuids1['encounters'][0]}, {'id': uuids2['encounters'][0]}]
    }
    ind_resp = individual_utils.create_individual(
        flask_app_client, researcher_1, data_in=ind_data
    ).json
    individual_utils.delete_individual(flask_app_client, researcher_1, ind_resp['guid'])


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
@pytest.mark.parametrize('sex', (None, 'male'))
def test_create_individual_sex(db, flask_app_client, request, sex):
    temp_owner = utils.generate_user_instance(
        email='owner@localhost',
        is_researcher=True,
    )
    request.addfinalizer(lambda: db.session.delete(temp_owner))

    temp_enc = utils.generate_encounter_instance(
        user_email='enc@user', user_password='encuser', user_full_name='enc user 1'
    )
    request.addfinalizer(lambda: db.session.delete(temp_enc))
    encounter_json = {'encounters': [{'id': str(temp_enc.guid)}], 'sex': sex}
    temp_enc.owner = temp_owner
    response = individual_utils.create_individual(
        flask_app_client, temp_owner, expected_status_code=200, data_in=encounter_json
    )
    individual_guid = response.json['guid']

    assert individual_guid is not None

    request.addfinalizer(
        lambda: individual_utils.delete_individual(
            flask_app_client, temp_owner, individual_guid
        )
    )

    read_individual = individual_utils.read_individual(
        flask_app_client, temp_owner, individual_guid
    )
    assert read_individual.json['sex'] == sex
    assert read_individual is not None
