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


@pytest.mark.only_for_codex
class TestAssetGroupConfig:
    @property
    def target_cls(self):
        from config.base import AssetGroupConfig

        return AssetGroupConfig

    def test_GIT_SSH_KEY_FILEPATH_without_key(self, monkeypatch):
        # Set the sceario where gitlab isn't in use
        #: using setattr because the class loads by env-var on declaration
        monkeypatch.setattr(self.target_cls, 'GIT_SSH_KEY', None)

        # Target
        config = self.target_cls()

        # Check the property is the default
        assert config.GIT_SSH_KEY_FILEPATH == self.target_cls.default_git_ssh_key_filepath

    def test_GIT_SSH_KEY_FILEPATH_with_existing_file(self, monkeypatch, tmp_path):
        # Set the sceario where the ssh key is set,
        # but the id_ssh_key file already exists.
        id_ssh_key_filepath = tmp_path / 'id_ssh_key'
        ssh_key = '--file based key--'
        with id_ssh_key_filepath.open('w') as fb:
            fb.write(ssh_key)
        perm_bits = 0o644
        id_ssh_key_filepath.chmod(perm_bits)
        monkeypatch.setenv('GIT_SSH_KEY_FILEPATH', str(id_ssh_key_filepath))
        #: using setattr because the class loads by env-var on declaration
        monkeypatch.setattr(self.target_cls, 'GIT_SSH_KEY', '--key--')

        # Target
        config = self.target_cls()

        # Check the property is the as env set
        assert config.GIT_SSH_KEY_FILEPATH == id_ssh_key_filepath
        # Check the file was not overwritten
        with id_ssh_key_filepath.open('r') as fb:
            assert fb.read() == ssh_key
        assert id_ssh_key_filepath.stat().st_mode == 33188  # i.e. 644

    def test_GIT_SSH_KEY_FILEPATH_without_existing_file(self, monkeypatch, tmp_path):
        # Set the sceario where the ssh key is set,
        # but the id_ssh_key file already exists.
        id_ssh_key_filepath = tmp_path / 'id_ssh_key'
        monkeypatch.setenv('GIT_SSH_KEY_FILEPATH', str(id_ssh_key_filepath))
        ssh_key = '--key--'
        #: using setattr because the class loads by env-var on declaration
        monkeypatch.setattr(self.target_cls, 'GIT_SSH_KEY', ssh_key)

        # Target
        config = self.target_cls()

        # Check the property is the as env set
        assert config.GIT_SSH_KEY_FILEPATH == id_ssh_key_filepath
        # Check the file was not overwritten
        with id_ssh_key_filepath.open('r') as fb:
            assert fb.read() == f'{ssh_key}\n'
        assert id_ssh_key_filepath.stat().st_mode == 33024  # i.e. 400
