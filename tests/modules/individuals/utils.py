# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.asset_groups.resources import utils as ags_utils


# this is just a flimsy wrapper now; do not use.  use create_asset_group_with_sighting_and_individual() instead


def simple_sighting_encounter(
    db, flask_app_client, user, request, test_root=None, individual_sex='female'
):
    (
        asset_group,
        sightings,
        individual,
    ) = ags_utils.create_asset_group_with_sighting_and_individual(
        flask_app_client,
        user,
        request,
        test_root=test_root,
    )
    # munge to fit previous expected return values
    assert len(sightings) > 0
    assert len(sightings[0].encounters) > 0
    return sightings[0], sightings[0].encounters[0]
