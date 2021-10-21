# -*- coding: utf-8 -*-
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_get_submission_not_found(flask_app_client):
    response = flask_app_client.get('/api/v1/submissions/wrong-uuid')
    assert response.status_code == 404
