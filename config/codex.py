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
    )
    # fmt: on

    # fmt: off
    # THIS ORDERING IS VERY SPECIFIC AND INFLUENCES WHICH MODULES CAN DEPEND ON EACH OTHER
    ENABLED_MODULES = (
        # Users
        #   Dependencies: [NONE]
        'users',

        # Organizations
        #   Dependencies: Users
        #
        #   Note: Organization defines a many-to-many relationship with User
        #         and will import app.modules.organizations.models when the
        #         User module and object are imported.  Disabling the
        #         'organizations' modules will currently break the implementation
        #         of the User model because it creates a broken backref
        'organizations',

        # Authentication
        #   Dependencies: Users
        'auth',

        # Asset_groups
        #   Dependencies: Users
        'asset_groups',

        # Assets
        #   Dependencies: Asset_groups
        'assets',

        # Miscellaneous
        'keywords',
        'fileuploads',
        'collaborations',
        'notifications',
        'encounters',
        'projects',
        'sightings',
        'individuals',
        'names',
        'annotations',
        'social_groups',
        'site_settings',
        'site_info',
        'job_control',
        'elasticsearch_proxy',
        'elasticsearch',

        # Front-end
        #   Dependencies: Users, Auth, Assets
        'frontend_ui',
        'app_ui',
        'swagger_ui',

        # REST APIs = API, Passthroughs, Configuration
        #   Dependencies: Users, Auth
        'api',
        'passthroughs',
        'configuration',
        'audit_logs',

        # MWS
        'missions',
    )
    # fmt: on


class ProductionConfig(BaseCodexConfig):
    BASE_URL = os.environ.get('HOUSTON_URL')

    MAIL_BASE_URL = BASE_URL
    MAIL_OVERRIDE_RECIPIENTS = None
    MAIL_ERROR_RECIPIENTS = [
        'mail-errors@wildme.org',
    ]

    SENTRY_DSN = os.getenv('SENTRY_DSN')


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
