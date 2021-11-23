# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

import config
from app import create_app


@pytest.fixture(autouse=True)
def unset_environment_variables(monkeypatch):
    """Don't allow the globally set ``FLASK_ENV``
    or ``HOUSTON_APP_CONTEXT`` environment variables
    influence the testing context.

    """
    monkeypatch.delenv(config.CONTEXT_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.delenv('FLASK_ENV', raising=False)


@pytest.mark.parametrize('context', config.VALID_CONTEXTS)
def test_create_app(context):
    create_app(context=context, testing=True)


class FauxConfig:
    """Fake of the configuration class created by config.configure"""

    def __init__(self, context, environment):
        # Do not add to this initialization method.
        # If you need a computeded value, use the `@property` method decorator.
        self.PROJECT_CONTEXT = context
        self.PROJECT_ENVIRONMENT = environment

    REDIS_HOST = 'redis'
    FAUX = True


def faux_configure_app(app, context=None, environment=None):
    """fake of config.configure_app"""
    app.config.from_object(FauxConfig(context, environment))


@pytest.mark.parametrize(
    'context, environment',
    sorted(list(zip(config.VALID_CONTEXTS * 3, config.VALID_ENVIRONMENTS * 3))),
)
def test_create_app_with_context_and_environment(monkeypatch, context, environment):
    # monkeypatched b/c we aren't trying to test configuring the app
    import app

    monkeypatch.setattr(app, 'configure_app', faux_configure_app)

    # Target
    a = create_app(context=context, environment=environment, testing=True)

    # Test the setting of the context and environment
    assert a.config['PROJECT_CONTEXT'] == context
    assert a.config['PROJECT_ENVIRONMENT'] == environment
    # Test for the setting that wouldn't appear in an actually settings object
    assert a.config['FAUX']


def test_create_app_specific_config(monkeypatch):
    monkeypatch.setenv('FLASK_ENV', 'production')
    # specificity at the function level is honored
    app = create_app(context='codex', environment='development', testing=True)
    # Test the environment variable was ignored ...
    assert app.config.get('DEBUG')  # using 'development'
