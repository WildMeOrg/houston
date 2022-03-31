# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging
import pytest
from tests.utils import module_unavailable

import tests.modules.integrity.resources.utils as integ_utils
import tests.modules.individuals.resources.utils as ind_utils

log = logging.getLogger(__name__)


@pytest.mark.skipif(module_unavailable('integrity'), reason='Integrity module disabled')
def test_basic_operation(
    db, flask_app_client, researcher_1, researcher_2, admin_user, request, test_root
):
    uuids = ind_utils.create_individual_and_sighting(
        flask_app_client, researcher_1, request, test_root
    )
    integ_utils.create(
        flask_app_client,
        researcher_1,
        403,
        "You don't have the permission to access the requested resource.",
    )
    integ_resp = integ_utils.create(flask_app_client, admin_user, request=request).json
    integ_guid = integ_resp['guid']

    assert {
        'asset_guids': [uuids['assets'][0]],
        'group_guid': uuids['asset_group'],
    } in integ_resp['result']['asset_groups']['assets_without_annots']
    assert uuids['assets'][0] in integ_resp['result']['assets']['no_content_guid']

    integ_utils.read_all(flask_app_client, researcher_1, 403)
    all_integs = integ_utils.read_all(flask_app_client, admin_user).json
    integ_guids = [check['guid'] for check in all_integs]
    assert integ_guid in integ_guids


@pytest.mark.skipif(module_unavailable('integrity'), reason='Integrity module disabled')
def test_errors(
    db, flask_app_client, researcher_1, researcher_2, admin_user, request, test_root
):
    guids = ind_utils.create_individual_and_sighting(
        flask_app_client, researcher_1, request, test_root
    )
    from app.modules.individuals.models import Individual

    indy = Individual.query.get(guids['individual'])
    old_encounters = indy.encounters
    indy.encounters = []

    integ_resp = integ_utils.create(flask_app_client, admin_user, request=request).json
    assert guids['individual'] in integ_resp['result']['individuals']['no_encounters']

    # Need to restore old encounters as without them, researcher_1 (who owns the encounters)
    # cannot delete the individual
    indy.encounters = old_encounters

    from app.modules.sightings.models import Sighting

    sight = Sighting.query.get(guids['sighting'])
    old_encounters = sight.encounters
    sight.encounters = []
    integ_resp = integ_utils.create(flask_app_client, admin_user, request=request).json
    assert guids['sighting'] in integ_resp['result']['sightings']['no_encounters'][0]

    # encounters not cleared up unless this is restored
    sight.encounters = old_encounters
