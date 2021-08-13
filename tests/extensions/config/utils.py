# -*- coding: utf-8 -*-
def get_and_check_houston_configs(key=None, value=None):
    from app.extensions.config.models import HoustonConfig

    current_houston_configs = HoustonConfig.query.all()

    if len(current_houston_configs) == 0:
        assert key is None and value is None
    else:
        assert len(current_houston_configs) == 1
        current_houston_config = current_houston_configs[0]
        assert current_houston_config.key == key
        assert current_houston_config.value == value


def delete_all_houston_configs(db):
    from app.extensions.config.models import HoustonConfig

    with db.session.begin():
        current_houston_configs = HoustonConfig.query.all()
        for current_houston_config in current_houston_configs:
            db.session.delete(current_houston_config)

    current_houston_configs = HoustonConfig.query.all()
    assert len(current_houston_configs) == 0


def check_inside_db_context(flask_app, db_app=None):
    assert flask_app.config.db_init
    assert flask_app.config.db_update
    if db_app is None:
        assert flask_app.config.db_app is None
    else:
        assert flask_app.config.db_app is not None
        assert flask_app.config.db_app == db_app


def check_outside_db_context(flask_app):
    assert flask_app.config.db_init
    assert not flask_app.config.db_update
    assert flask_app.config.db_app is None


def get_and_check_detection_config(flask_app_client):
    path = '/api/v1/config/detection/'
    response = flask_app_client.get(path)
    assert response['success'] is True
