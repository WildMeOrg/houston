# -*- coding: utf-8 -*-
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('projects'), reason='Projects module disabled')
def test_get_project_not_found(flask_app_client):
    response = flask_app_client.get('/api/v1/projects/wrong-uuid')
    assert response.status_code == 404
