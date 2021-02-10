# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

from app import CONFIG_NAME_MAPPER, create_app


@pytest.fixture(autouse=True)
def unset_FLASK_CONFIG(monkeypatch):
    """Don't allow a globally set ``FLASK_CONFIG`` environ var
    to influence the testing context

    """
    monkeypatch.delenv('FLASK_CONFIG', raising=False)


def test_create_app():
    try:
        create_app(testing=True)
    except SystemExit:
        # Clean git repository doesn't have `local_config.py`, so it is fine
        # if we get SystemExit error.
        pass


@pytest.mark.parametrize('flask_config_name', ['production', 'development', 'testing'])
def test_create_app_passing_flask_config_name(monkeypatch, flask_config_name):
    if flask_config_name == 'production':
        from config import ProductionConfig

        monkeypatch.setattr(ProductionConfig, 'SQLALCHEMY_DATABASE_URI', 'sqlite://')
        monkeypatch.setattr(ProductionConfig, 'SECRET_KEY', 'secret', raising=False)
    create_app(flask_config_name=flask_config_name, testing=True)


@pytest.mark.parametrize('flask_config_name', ['production', 'development', 'testing'])
def test_create_app_passing_FLASK_CONFIG_env(monkeypatch, flask_config_name):
    monkeypatch.setenv('FLASK_CONFIG', flask_config_name)
    if flask_config_name == 'production':
        from config import ProductionConfig

        monkeypatch.setattr(ProductionConfig, 'SQLALCHEMY_DATABASE_URI', 'sqlite://')
        monkeypatch.setattr(ProductionConfig, 'SECRET_KEY', 'secret', raising=False)
    create_app(testing=True)


def test_create_app_with_conflicting_config(monkeypatch):
    monkeypatch.setenv('FLASK_CONFIG', 'production')
    with pytest.raises(AssertionError):
        create_app('development', testing=True)


def test_create_app_with_non_existing_config():
    with pytest.raises(KeyError):
        create_app('non-existing-config', testing=True)


def test_create_app_with_broken_import_config():
    CONFIG_NAME_MAPPER['broken-import-config'] = 'broken-import-config'
    with pytest.raises(ImportError):
        create_app('broken-import-config', testing=True)
    del CONFIG_NAME_MAPPER['broken-import-config']
