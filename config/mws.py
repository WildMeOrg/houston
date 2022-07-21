# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods,invalid-name,missing-docstring
from .base import (
    DATA_ROOT,
    AssetGroupConfig,
    BaseConfig,
    ElasticsearchConfig,
    EmailConfig,
    FlatfileConfig,
    GoogleConfig,
    ReCaptchaConfig,
    SageConfig,
    SentryConfig,
    TransloaditConfig,
    WildbookDatabaseConfig,
)
from .utils import _getenv


class BaseMWSConfig(
    BaseConfig,
    EmailConfig,
    ReCaptchaConfig,
    GoogleConfig,
    SageConfig,
    AssetGroupConfig,
    ElasticsearchConfig,
    WildbookDatabaseConfig,
    FlatfileConfig,
    TransloaditConfig,
    SentryConfig,
):
    PROJECT_NAME = 'MWS'

    MISSION_COLLECTION_DATABASE_PATH = str(DATA_ROOT / 'mission_collection')

    # fmt: off
    ENABLED_EXTENSIONS = (
        'sage',
        'cors',
        'elasticsearch',
        'tus',
        'mail',
        'gitlab',
        'sentry',
        'prometheus',
    )

    ENABLED_MODULES = (
        'users',
        'auth',
        'assets',

        'keywords',
        'fileuploads',
        'notifications',
        'complex_date_time',
        'annotations',
        'missions',
        'site_settings',
        'job_control',

        'app_ui',
        'swagger_ui',

        'emails',
        'audit_logs',
        'progress',
    )
    # fmt: on

    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # Maximum size of 100MB


class ProductionConfig(BaseMWSConfig):
    TESTING = False

    MAIL_OVERRIDE_RECIPIENTS = None
    MAIL_ERROR_RECIPIENTS = [
        'mail-errors@wildme.org',
    ]


class DevelopmentConfig(BaseMWSConfig):
    DEBUG = True

    MAIL_OVERRIDE_RECIPIENTS = _getenv(
        'MAIL_OVERRIDE_RECIPIENTS', 'testing@wildme.org'
    ).split(',')
    MAIL_ERROR_RECIPIENTS = _getenv(
        'MAIL_ERROR_RECIPIENTS', 'mail-errors@wildme.org'
    ).split(',')

    SECRET_KEY = 'DEVELOPMENT_SECRET_KEY'


class TestingConfig(DevelopmentConfig):
    TESTING = True

    # Use in-memory database for testing if SQLALCHEMY_DATABASE_URI and TEST_DATABASE_URI are not specified
    SQLALCHEMY_DATABASE_URI = _getenv('TEST_DATABASE_URI') or _getenv(
        'SQLALCHEMY_DATABASE_URI'
    )

    MAIL_SUPPRESS_SEND = True
