# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring


def test_project_remove_encounters(
    db, researcher_1, researcher_1_login, test_empty_submission_uuid
):  # pylint: disable=unused-argument
    # pylint: disable=unused-argument
    from app.modules.projects.parameters import PatchProjectDetailsParameters
    from app.modules.projects.models import Project

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
            temp_proj, 'encounter', test_empty_submission_uuid, state
        )
        is False
    )

    with db.session.begin():
        db.session.delete(temp_proj)
