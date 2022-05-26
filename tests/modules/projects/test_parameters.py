# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('projects'), reason='Projects module disabled')
def test_project_remove_encounters(
    db, researcher_1, researcher_1_login, test_empty_asset_group_uuid
):  # pylint: disable=unused-argument
    # pylint: disable=unused-argument
    from app.modules.asset_groups.models import AssetGroup
    from app.modules.projects.models import Project
    from app.modules.projects.parameters import PatchProjectDetailsParameters

    temp_proj = Project(
        title='Temp Project',
        owner_guid=researcher_1.guid,
    )

    with db.session.begin():
        db.session.add(temp_proj)

    db.session.refresh(temp_proj)
    state = {'current_password': 'Any value will do'}

    # Use a dummy guid to test this, don't need an actual encounter
    assert (
        PatchProjectDetailsParameters.remove(
            temp_proj, 'encounter', test_empty_asset_group_uuid, state
        )
        is False
    )

    with db.session.begin():
        db.session.delete(temp_proj)
        AssetGroup.query.get(test_empty_asset_group_uuid).delete()
