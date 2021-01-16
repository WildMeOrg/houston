# -*- coding: utf-8 -*-


def test_set_db_config(flask_app, db):
    from app.extensions.config import HoustonFlaskConfig
    from app.extensions.config.models import HoustonConfig

    try:
        # Ensure this config is empty and ENV is the value 'production'
        assert flask_app.config['ENV'] == 'production'
        current_houston_configs = HoustonConfig.query.all()
        assert len(current_houston_configs) == 0

        assert isinstance(flask_app.config, HoustonFlaskConfig)
        assert flask_app.config.db_init
        assert not flask_app.config.db_update
        assert flask_app.config.db_app is None

        # First, check (current_app) environment is setup and torn down correctly by context
        with flask_app.config.db():
            assert flask_app.config.db_init
            assert flask_app.config.db_update
            assert flask_app.config.db_app is None
        assert not flask_app.config.db_update
        assert flask_app.config.db_app is None

        # Second, check if a specific app environment works correclt
        with flask_app.config.db(flask_app):
            assert flask_app.config.db_init
            assert flask_app.config.db_update
            assert flask_app.config.db_app is not None
            assert flask_app.config.db_app == flask_app
        assert not flask_app.config.db_update
        assert flask_app.config.db_app is None

        # Update config, ensure no database update
        new_env = 'testing-no-db'
        flask_app.config['ENV'] = new_env
        assert flask_app.config['ENV'] == new_env

        current_houston_configs = HoustonConfig.query.all()
        assert len(current_houston_configs) == 0

        # Update with database
        new_env = 'testing-with-db'
        with flask_app.config.db(flask_app):
            flask_app.config['ENV'] = new_env
        assert not flask_app.config.db_update
        assert flask_app.config.db_app is None
        assert flask_app.config['ENV'] == new_env

        current_houston_configs = HoustonConfig.query.all()
        assert len(current_houston_configs) == 1
        current_houston_config = current_houston_configs[0]
        assert current_houston_config.key == 'ENV'
        assert current_houston_config.value == new_env
    finally:
        flask_app.config['ENV'] = 'production'

        with db.session.begin():
            current_houston_configs = HoustonConfig.query.all()
            for current_houston_config in current_houston_configs:
                db.session.delete(current_houston_config)

        current_houston_configs = HoustonConfig.query.all()
        assert len(current_houston_configs) == 0


def test_forget_db_config(flask_app, db):
    from app.extensions.config.models import HoustonConfig

    # Ensure this config is empty and ENV is the value 'production'
    assert flask_app.config['ENV'] == 'production'
    current_houston_configs = HoustonConfig.query.all()
    assert len(current_houston_configs) == 0

    # Update with database
    new_env = 'testing-with-db'
    with flask_app.config.db(flask_app):
        flask_app.config['ENV'] = new_env
    assert not flask_app.config.db_update
    assert flask_app.config.db_app is None
    assert flask_app.config['ENV'] == new_env

    current_houston_configs = HoustonConfig.query.all()
    assert len(current_houston_configs) == 1
    current_houston_config = current_houston_configs[0]
    assert current_houston_config.key == 'ENV'
    assert current_houston_config.value == new_env

    # Delete (by forgetting) the database value override for this configuration
    flask_app.config.forget('ENV')

    current_houston_configs = HoustonConfig.query.all()
    assert len(current_houston_configs) == 0
