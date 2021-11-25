# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

from config import (
    configure_app,
    CONFIG_CLS_MAPPER,
    CONTEXT_ENVIRONMENT_VARIABLE,
    get_preliminary_config,
    VALID_CONTEXTS,
    VALID_ENVIRONMENTS,
)
from config.utils import import_class


@pytest.fixture(autouse=True)
def unset_environment_variables(monkeypatch):
    """Don't allow the globally set ``FLASK_ENV``
    or ``HOUSTON_APP_CONTEXT`` environment variables
    influence the testing context.

    """
    monkeypatch.delenv(CONTEXT_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.delenv('FLASK_ENV', raising=False)


@pytest.fixture(autouse=True)
def clear_get_preliminary_config_cache():
    """The target function is cached by parameters,
    so we clear the cache before starting.
    Note, in most production use case the caching,
    even of the no parameters usage, is desired.

    """
    get_preliminary_config.cache_clear()
    yield
    get_preliminary_config.cache_clear()


context_and_environment_params = pytest.mark.parametrize(
    'context, environment',
    sorted(list(zip(VALID_CONTEXTS * 3, VALID_ENVIRONMENTS * 3))),
)


@context_and_environment_params
def test_get_preliminary_config_from_env_vars(monkeypatch, context, environment):
    monkeypatch.setenv(CONTEXT_ENVIRONMENT_VARIABLE, context)
    monkeypatch.setenv('FLASK_ENV', environment)
    # Assume the configuration class mapping is correct
    expected_cls = import_class(CONFIG_CLS_MAPPER[context][environment])

    # Target
    config = get_preliminary_config()

    assert isinstance(config, expected_cls)
    assert config.PROJECT_CONTEXT == context
    assert config.PROJECT_ENVIRONMENT == environment


@context_and_environment_params
def test_get_preliminary_config_from_parameters(monkeypatch, context, environment):
    # Assume the configuration class mapping is correct
    expected_cls = import_class(CONFIG_CLS_MAPPER[context][environment])

    # Target
    config = get_preliminary_config(context=context, environment=environment)

    assert isinstance(config, expected_cls)
    assert config.PROJECT_CONTEXT == context
    assert config.PROJECT_ENVIRONMENT == environment


def test_get_preliminary_config_with_missing_context():
    environment = 'production'
    with pytest.raises(RuntimeError) as exc_info:
        # Target
        get_preliminary_config(environment=environment)

    # Check the exception for part of the human readable message
    exc = exc_info.value
    assert 'application context must be defined' in exc.args[0]


def test_get_preliminary_config_with_invalid_environment():
    context = 'codex'
    environment = 'invalid'
    with pytest.raises(RuntimeError) as exc_info:
        # Target
        get_preliminary_config(context=context, environment=environment)

    # Check the exception for part of the human readable message
    exc = exc_info.value
    assert 'Flask environment must be defined' in exc.args[0]


def test_configure_app_with_parameters():
    import flask

    app = flask.Flask('testing')
    context = 'codex'
    environment = 'development'

    # Target
    configure_app(app, context=context, environment=environment)

    # Check the configuration is loaded
    assert app.config['PROJECT_CONTEXT'] == context
    assert app.config['PROJECT_ENVIRONMENT'] == environment


def test_configure_app_from_env_vars(monkeypatch):
    import flask

    app = flask.Flask('testing')
    context = 'codex'
    environment = 'development'
    monkeypatch.setenv(CONTEXT_ENVIRONMENT_VARIABLE, context)
    monkeypatch.setenv('FLASK_ENV', environment)

    # Target
    configure_app(app)

    # Check the configuration is loaded
    assert app.config['PROJECT_CONTEXT'] == context
    assert app.config['PROJECT_ENVIRONMENT'] == environment
