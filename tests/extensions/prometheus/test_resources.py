# -*- coding: utf-8 -*-
import json

import pytest

from app.extensions.prometheus import update
from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test(flask_app, flask_app_client):
    from app.modules.users.models import User

    client = flask_app.test_client()

    user = User.query.filter(
        User.email == flask_app.config['OAUTH_USER']['email']
    ).first()
    with flask_app_client.login(
        user, auth_scopes=('prometheus:read', 'prometheus:write')
    ):
        data = json.dumps(update())
        response = flask_app_client.post('/api/v1/prometheus/', json=data)
        assert response.status_code == 200

    response = client.get('/metrics')
    lines = response.data.decode('utf-8').splitlines()
    models_line = [line for line in lines if line.startswith('models')]
    assert models_line
    logins_lines = [line for line in lines if line.startswith('logins')]
    assert logins_lines
