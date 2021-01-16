# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import json


def test_modifying_db_config_by_admin(flask_app_client, admin_user, db):
    # pylint: disable=invalid-name
    from app.extensions.config.models import HoustonConfig

    try:
        current_houston_configs = HoustonConfig.query.all()
        assert len(current_houston_configs) == 0

        new_env = 'testing-with-db'

        with flask_app_client.login(admin_user, auth_scopes=('config.houston:write',)):
            response = flask_app_client.patch(
                '/api/v1/config/houston/',
                content_type='application/json',
                data=json.dumps(
                    [
                        {
                            'op': 'test',
                            'path': '/current_password',
                            'value': admin_user.password_secret,
                        },
                        {
                            'op': 'add',
                            'path': '/ENV',
                            'value': new_env,
                        },
                    ]
                ),
            )

        assert response.json

        current_houston_configs = HoustonConfig.query.all()
        assert len(current_houston_configs) == 1
        current_houston_config = current_houston_configs[0]
        assert current_houston_config.key == 'ENV'
        assert current_houston_config.value == new_env

        with flask_app_client.login(admin_user, auth_scopes=('config.houston:write',)):
            response = flask_app_client.patch(
                '/api/v1/config/houston/',
                content_type='application/json',
                data=json.dumps(
                    [
                        {
                            'op': 'test',
                            'path': '/current_password',
                            'value': admin_user.password_secret,
                        },
                        {
                            'op': 'remove',
                            'path': '/ENV',
                        },
                    ]
                ),
            )

        assert response.json

        current_houston_configs = HoustonConfig.query.all()
        assert len(current_houston_configs) == 0
    except Exception as ex:
        raise ex
    finally:
        with db.session.begin():
            current_houston_configs = HoustonConfig.query.all()
            for current_houston_config in current_houston_configs:
                db.session.delete(current_houston_config)
