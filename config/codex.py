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


class BaseCodexConfig(
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
    PROJECT_NAME = 'Codex'

    ASSET_GROUP_DATABASE_PATH = str(DATA_ROOT / 'asset_group')

    # fmt: off
    ENABLED_EXTENSIONS = (
        'acm',
        'edm',
        'cors',
        'elasticsearch',
        'gitlab',
        'tus',
        'mail',
        'stripe',
        'sentry',
    )

    ENABLED_MODULES = (
        'users',
        'organizations',
        'auth',
        'asset_groups',
        'assets',

        'keywords',
        'fileuploads',
        'collaborations',
        'notifications',
        'encounters',
        'projects',
        'sightings',
        'individuals',
        'relationships',
        'names',
        'complex_date_time',
        'annotations',
        'social_groups',
        'site_settings',
        'job_control',
        'elasticsearch_proxy',
        'elasticsearch',

        'app_ui',
        'swagger_ui',

        'api',
        'passthroughs',
        'emails',
        'audit_logs',
    )
    # fmt: on


class ProductionConfig(BaseCodexConfig):
    TESTING = False

    BASE_URL = os.environ.get('HOUSTON_URL')

    MAIL_BASE_URL = BASE_URL
    MAIL_OVERRIDE_RECIPIENTS = None
    MAIL_ERROR_RECIPIENTS = [
        'mail-errors@wildme.org',
    ]

    SENTRY_DSN = os.getenv('SENTRY_DSN_PRODUCTION', None)


class DevelopmentConfig(BaseCodexConfig):
    DEBUG = True

    BASE_URL = os.environ.get('HOUSTON_URL', 'https://wildme.ngrok.io/')

    MAIL_BASE_URL = BASE_URL
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
