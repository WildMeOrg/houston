# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods,invalid-name,missing-docstring
import os

from .base import (
    ACMConfig,
    AssetGroupConfig,
    BaseConfig,
    EDMConfig,
    ElasticsearchConfig,
    EmailConfig,
    GoogleConfig,
    ReCaptchaConfig,
    WildbookDatabaseConfig,
    DATA_ROOT,
)


class BaseMWSConfig(
    BaseConfig,
    EmailConfig,
    ReCaptchaConfig,
    GoogleConfig,
    ACMConfig,
    EDMConfig,
    AssetGroupConfig,
    ElasticsearchConfig,
    WildbookDatabaseConfig,
):
    PROJECT_NAME = 'MWS'

    MISSION_COLLECTION_DATABASE_PATH = str(DATA_ROOT / 'mission_collection')

    # fmt: off
    ENABLED_EXTENSIONS = (
        'acm',
        'cors',
        'elasticsearch',
        'tus',
        'mail',
        'gitlab',
        'sentry',
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
        'elasticsearch',

        'app_ui',
        'swagger_ui',

        'api',
        'emails',
        'audit_logs',
    )
    # fmt: on

    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # Maximum size of 100MB


class ProductionConfig(BaseMWSConfig):
    TESTING = False

    MAIL_OVERRIDE_RECIPIENTS = None
    MAIL_ERROR_RECIPIENTS = [
        'mail-errors@wildme.org',
    ]

    SENTRY_DSN = os.getenv('SENTRY_DSN_PRODUCTION', None)


class DevelopmentConfig(BaseMWSConfig):
    DEBUG = True

    MAIL_OVERRIDE_RECIPIENTS = [
        'testing@wildme.org',
    ]
    MAIL_ERROR_RECIPIENTS = [
        'mail-errors@wildme.org',
    ]

    SECRET_KEY = 'DEVELOPMENT_SECRET_KEY'
    SENTRY_DSN = os.getenv('SENTRY_DSN_DEVELOPMENT', None)


class TestingConfig(DevelopmentConfig):
    TESTING = True

    # Use in-memory SQLite database for testing if SQLALCHEMY_DATABASE_URI and TEST_DATABASE_URI are not specified
    SQLALCHEMY_DATABASE_URI = (
        os.getenv('TEST_DATABASE_URI')
        or os.getenv('SQLALCHEMY_DATABASE_URI')
        or 'sqlite://'
    )

    MAIL_SUPPRESS_SEND = True
