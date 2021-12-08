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
    # fmt: off
    ENABLED_EXTENSIONS = (
        'acm',
        'cors',
        'elasticsearch',
        'tus',
        'mail',
    )
    # fmt: on

    # fmt: off
    # THIS ORDERING IS VERY SPECIFIC AND INFLUENCES WHICH MODULES CAN DEPEND ON EACH OTHER
    ENABLED_MODULES = (
        # Users
        #   Dependencies: [NONE]
        'users',

        # Authentication
        #   Dependencies: Users
        'auth',

        # Assets
        #   Dependencies: Asset_groups
        'assets',

        # Miscellaneous
        'keywords',
        'fileuploads',
        'notifications',
        'annotations',
        'missions',
        'site_settings',
        'site_info',
        'job_control',

        # Elastic Search
        'elasticsearch_proxy',
        'elasticsearch',

        # Front-end
        #   Dependencies: Users, Auth, Assets
        'app_ui',
        'swagger_ui',

        # REST APIs = API, Passthroughs, Configuration
        #   Dependencies: Users, Auth
        'api',
        'audit_logs',
    )
    # fmt: on


class ProductionConfig(BaseMWSConfig):
    TESTING = False

    BASE_URL = os.environ.get('HOUSTON_URL')

    MAIL_BASE_URL = BASE_URL
    MAIL_OVERRIDE_RECIPIENTS = None
    MAIL_ERROR_RECIPIENTS = [
        'parham@wildme.org',
    ]

    SENTRY_DSN = os.getenv('SENTRY_DSN')


class DevelopmentConfig(BaseMWSConfig):
    DEBUG = True

    BASE_URL = os.environ.get('HOUSTON_URL', 'https://wildme.ngrok.io/')

    MAIL_BASE_URL = BASE_URL
    MAIL_OVERRIDE_RECIPIENTS = [
        'parham@wildme.org',
    ]
    MAIL_ERROR_RECIPIENTS = [
        'parham@wildme.org',
    ]

    SECRET_KEY = 'DEVELOPMENT_SECRET_KEY'
    SENTRY_DSN = None


class TestingConfig(DevelopmentConfig):
    TESTING = True

    # Use in-memory SQLite database for testing if SQLALCHEMY_DATABASE_URI and TEST_DATABASE_URI are not specified
    SQLALCHEMY_DATABASE_URI = (
        os.getenv('TEST_DATABASE_URI')
        or os.getenv('SQLALCHEMY_DATABASE_URI')
        or 'sqlite://'
    )

    MAIL_SUPPRESS_SEND = True
