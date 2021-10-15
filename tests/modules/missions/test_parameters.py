# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring


def test_mission_remove_encounters(
    db, researcher_1, researcher_1_login, test_empty_asset_group_uuid
):  # pylint: disable=unused-argument
    # pylint: disable=unused-argument
    from app.modules.asset_groups.models import AssetGroup
    from app.modules.missions.parameters import PatchMissionDetailsParameters
    from app.modules.missions.models import Mission

    temp_proj = Mission(
        title='Temp Mission',
        owner_guid=researcher_1.guid,
    )

    with db.session.begin():
        db.session.add(temp_proj)

    db.session.refresh(temp_proj)
    state = {'current_password': 'Any value will do'}

    # Use a dummy guid to test this, don't need an actual encounter
    assert (
        PatchMissionDetailsParameters.remove(
            temp_proj, 'encounter', test_empty_asset_group_uuid, state
        )
        is False
    )

    with db.session.begin():
        db.session.delete(temp_proj)
        AssetGroup.query.get(test_empty_asset_group_uuid).delete()
