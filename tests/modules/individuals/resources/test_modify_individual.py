# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_modify_individual_edm_fields(
    db, flask_app_client, researcher_1, staff_user, request, test_root
):

    from app.modules.encounters.models import Encounter
    from app.modules.sightings.models import Sighting

    individual_json = None

    try:

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

        individual_data_in = {
            'names': [{'context': 'defaultName', 'value': 'Godzilla'}],
            'encounters': [
                {
                    'id': str(enc.guid),
                }
            ],
            'sex': 'female',
            'comments': 'Test Individual',
            'timeOfBirth': '872846040000',
        }

        individual_response = individual_utils.create_individual(
            flask_app_client, researcher_1, 200, individual_data_in
        )

        assert individual_response.json['result']['id'] is not None

        individual_id = individual_response.json['result']['id']

        individual_json = individual_utils.read_individual(
            flask_app_client, researcher_1, individual_id
        ).json

        assert individual_json['sex'] == 'female'
        assert len(individual_json['names']) == 1
        assert individual_json['names'][0]['context'] == 'defaultName'
        assert individual_json['names'][0]['value'] == 'Godzilla'
        assert individual_json['comments'] == 'Test Individual'

        # when skynet went online
        assert individual_json['timeOfBirth'] == '872846040000'

        patch_op_sex = [
            utils.patch_replace_op('sex', 'male'),
        ]
        # Absolute bare minimum validation, this is a debug output so will change
        debug_ind_data = individual_utils.read_individual(
            flask_app_client, staff_user, f'debug/{individual_id}'
        ).json
        assert debug_ind_data['guid'] == individual_id

        patch_individual_response = individual_utils.patch_individual(
            flask_app_client, researcher_1, individual_id, patch_op_sex
        )

        # back to the future 2 date
        patch_data = [
            utils.patch_replace_op('timeOfBirth', '1445410800000'),
        ]

        patch_individual_response = individual_utils.patch_individual(
            flask_app_client, researcher_1, individual_id, patch_data
        )

        assert patch_individual_response.json['guid'] is not None

        individual_json = individual_utils.read_individual(
            flask_app_client, researcher_1, patch_individual_response.json['guid']
        ).json

        assert individual_json['id'] is not None
        assert individual_json['sex'] == 'male'
        assert individual_json['timeOfBirth'] == '1445410800000'

    finally:
        individual_utils.delete_individual(
            flask_app_client, researcher_1, individual_json['id']
        )
        sighting.delete_cascade()
        enc.delete_cascade()
