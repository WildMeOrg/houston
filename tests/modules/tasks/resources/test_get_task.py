# -*- coding: utf-8 -*-
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('tasks'), reason='Tasks module disabled')
def test_get_task_not_found(flask_app_client):
    response = flask_app_client.get('/api/v1/tasks/wrong-uuid')
    assert response.status_code == 404
    response.close()
