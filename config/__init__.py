# -*- coding: utf-8 -*-
"""\
This package defines configuration for the Houston application and its various contexts. It also defines functions for determining which configuration to be used.

``HOUSTON_CONTEXT`` defines the context in which the houston application is being used, either 'codex' or 'mws'.

``FLASK_ENV`` defines the environment for which the Flask framework is to work within, either 'development', 'testing', or 'production'. See also the Flask framework's documentation around this variable.

The combination of ``HOUSTON_CONTEXT`` & ``FLASK_ENV`` are used to determine which configuration to use when running the application.

"""
import os
from functools import lru_cache
from pathlib import Path

from .utils import import_class, export_dotenv


CONTEXT_ENVIRONMENT_VARIABLE = 'HOUSTON_APP_CONTEXT'
CONFIG_CLS_MAPPER = {
    # context -> environment -> path to configuration class
    'codex': {
        'development': 'config.codex:DevelopmentConfig',
        'testing': 'config.codex:TestingConfig',
        'production': 'config.codex:ProductionConfig',
    },
    'mws': {
        'development': 'config.mws:DevelopmentConfig',
        'testing': 'config.mws:TestingConfig',
        'production': 'config.mws:ProductionConfig',
    },
}
VALID_CONTEXTS = tuple(CONFIG_CLS_MAPPER.keys())
VALID_ENVIRONMENTS = (
    'production',
    'testing',
    'development',
)


__all__ = (
    'configure_app',
    'get_preliminary_config',
)


# Cached preliminary configuration instance
_preliminary_config = None


@lru_cache
def get_preliminary_config(context=None, environment=None):
    """Returns the preliminary configuration for the given
    or discovered context and environment.
    This should only be used where it is necessary
    to obtain the configuration
    without it being contextualized with the Flask App instance.

    Note, this is a cached function that does not take
    the given ``context`` and ``environment`` into consideration
    when looking up the cache, because it it assumed that these are
    constant values throughout the life of the runtime.

    This function is also responsible for loading any environment variables
    from ``.env`` file(s).

    This is a preliminary configuration because the application factory
    may have other means of updating the configuration values
    (e.g. cli or database settings).

    """
    # Discover the application context
    ctx = context if context else os.getenv(CONTEXT_ENVIRONMENT_VARIABLE, '')
    ctx = ctx.lower()  # to unify the naming case
    if not ctx or ctx not in VALID_CONTEXTS:
        raise RuntimeError(
            'The application context must be defined using '
            f"'{CONTEXT_ENVIRONMENT_VARIABLE}' in an environment variable. "
            f"This value can be {' or '.join(VALID_CONTEXTS)}. "
        )
    # Reusing Flask's built in FLASK_ENV
    env = environment if environment else os.getenv('FLASK_ENV', 'production')
    env = env.lower()  # to unify the naming case
    if env not in VALID_ENVIRONMENTS:
        raise RuntimeError(
            'The Flask environment must be defined (i.e. as '
            f"'FLASK_ENV' in an environment variable) with one of "
            f"the following values: {' or '.join(VALID_ENVIRONMENTS)}."
        )

    # It's important to load the .env file prior to importing
    # the configuration class.
    export_dotenv([Path.cwd() / f'.env.{ctx}'])

    # Import the configuration class.
    config_cls = import_class(CONFIG_CLS_MAPPER[ctx][env])

    # Instantiate the configuration
    cfg = config_cls(ctx, env)
    return cfg


def configure_app(app, context=None, environment=None):
    """Configures the application"""
    # Instantiate and load the configuration into the application.
    cfg = get_preliminary_config(context, environment)

    config_cls = cfg.__class__
    app.logger.info(
        f"Creating 'app.config' for '{cfg.PROJECT_CONTEXT}' within the "
        f"'{cfg.PROJECT_ENVIRONMENT}' environment using the "
        f"'{config_cls!r}' configuration class"
    )
    app.config.from_object(cfg)
