# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods,invalid-name,missing-docstring
import os
import logging
import datetime
from pathlib import Path

import pytz
from dotenv import load_dotenv

import flask

log = logging.getLogger(__name__)

HERE = Path(__file__).parent

# Load .env into environment variables (then available under os.environ)
_DEFAULT_DOTENV = HERE / '.env'
_dotenv = os.getenv('HOUSTON_DOTENV', _DEFAULT_DOTENV)
load_dotenv(_dotenv, override=False)  # gracefully fails if file doesn't exist

PROJECT_ROOT = str(HERE)
DATA_ROOT = Path(os.getenv('DATA_ROOT', HERE / '_db'))


class BaseConfig(object):
    # SQLITE
    PROJECT_ROOT = PROJECT_ROOT
    PROJECT_DATABASE_PATH = str(DATA_ROOT)

    ASSET_GROUP_DATABASE_PATH = str(DATA_ROOT / 'asset_group')
    ASSET_MIME_TYPE_WHITELIST = [
        'application/json',
        'application/ld+json',
        'application/msword',
        'application/octet-stream',
        'application/ogg',
        'application/pdf',
        'application/rtf',
        'application/vnd.ms-excel',
        'application/vnd.oasis.opendocument.spreadsheet',
        'application/vnd.oasis.opendocument.text',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/xml',
        'image/bmp',
        'image/gif',
        'image/jpeg',
        'image/png',
        'image/tiff',
        'image/webp',
        'text/csv',
        'text/javascript',
        'text/plain',
        'text/xml',
        'video/mpeg',
        'video/ogg',
        'video/webm',
    ]

    ASSET_DATABASE_PATH = str(DATA_ROOT / 'assets')
    ASSET_ALLOWED_EXTS = [
        '.jpg',
        '.jpe',
        '.jpeg',
        '.png',
        '.gif',
        '.svg',
        '.bmp',
        '.tif',
        '.tiff',
    ]

    # specifically this is where tus "temporary" files go
    UPLOADS_DATABASE_PATH = str(DATA_ROOT / 'uploads')
    REDIS_HOST = os.getenv('REDIS_HOST') or 'localhost'

    FILEUPLOAD_BASE_PATH = os.path.join(PROJECT_DATABASE_PATH, 'fileuploads')

    # FIXME: There is code that won't allow for `SQLALCHEMY_DATABASE_PATH = None`
    #        File "/code/tasks/app/db.py", in upgrade: `if os.path.exists(_db_filepath):`
    # SQLALCHEMY_DATABASE_PATH = None
    SQLALCHEMY_DATABASE_PATH = str(DATA_ROOT / 'database.sqlite3')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI') or 'sqlite:///%s' % (
        SQLALCHEMY_DATABASE_PATH
    )

    DEBUG = False
    ERROR_404_HELP = False

    PREFERRED_URL_SCHEME = 'http'
    REVERSE_PROXY_SETUP = os.getenv('HOSTON_REVERSE_PROXY_SETUP', False)

    SECRET_KEY = os.getenv('SECRET_KEY')

    AUTHORIZATIONS = {
        'oauth2_password': {
            'type': 'oauth2',
            'flow': 'password',
            'scopes': {},
            'tokenUrl': '/api/v1/auth/tokens',
        },
    }

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
        'annotations',
        'site_settings',
        'site_info',
        'job_control',

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
    )
    # fmt: on

    STATIC_ROOT = os.path.join(PROJECT_ROOT, 'app', 'static')
    FRONTEND_DIST = os.getenv(
        'FRONTEND_DIST',
        os.path.join(PROJECT_ROOT, 'app', 'static', 'dist-latest'),
    )
    SWAGGER_UI_DIST = os.getenv(
        'SWAGGER_UI_DIST',
        os.path.join(PROJECT_ROOT, 'app', 'static', 'swagger-ui'),
    )

    SWAGGER_UI_JSONEDITOR = True
    SWAGGER_UI_OAUTH_CLIENT_ID = 'documentation'
    SWAGGER_UI_OAUTH_REALM = 'Authentication for Houston server documentation'
    SWAGGER_UI_OAUTH_APP_NAME = 'Houston server documentation'

    SQLALCHEMY_TRACK_MODIFICATIONS = True
    CSRF_ENABLED = True
    PREMAILER_CACHE_MAXSIZE = 1024

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Maximum size of 16MB

    PERMANENT_SESSION_LIFETIME = datetime.timedelta(days=7)
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = False
    SESSION_REFRESH_EACH_REQUEST = True

    REMEMBER_COOKIE_DURATION = datetime.timedelta(days=14)
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_REFRESH_EACH_REQUEST = True

    TIMEZONE = pytz.timezone('UTC')

    RESTX_JSON = {
        'cls': flask.json.JSONEncoder,
    }


class EmailConfig(object):
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = bool(os.getenv('MAIL_USE_TLS', True))
    MAIL_USE_SSL = bool(os.getenv('MAIL_USE_SSL', False))
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', 'dev@wildme.org')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', 'XXX')
    MAIL_DEFAULT_SENDER = (
        os.getenv('MAIL_DEFAULT_SENDER_NAME', 'Wild Me'),
        os.getenv('MAIL_DEFAULT_SENDER_EMAIL', 'dev@wildme.org'),
    )


class ReCaptchaConfig(object):
    RECAPTCHA_PUBLIC_KEY = os.getenv('RECAPTCHA_PUBLIC_KEY', 'XXX')
    RECAPTCHA_BYPASS = os.getenv('RECAPTCHA_BYPASS', 'XXX')


class StripeConfig(object):
    STRIPE_PUBLIC_KEY = 'pk_test_XXX'
    STRIPE_SECRET_KEY = 'sk_test_XXX'


class GoogleAnalyticsConfig(object):
    GOOGLE_ANALYTICS_TAG = 'G-XXX'


class GoogleMapsConfig(object):
    GOOGLE_MAP_API_KEY = 'XXX'


class GoogleConfig(GoogleAnalyticsConfig, GoogleMapsConfig):
    pass


def get_env_rest_config(interface):
    """Parse ACM/EDM configuration from environment variables"""
    # Parse all uris from environment variables
    uris = {}
    for varname in [
        e for e in os.environ if e.startswith(f'{interface}_AUTHENTICATIONS_URI__')
    ]:
        #: e.g. ACM_AUTHENTICATIONS_URI__DEFAULT
        key = varname.split('__')[-1].lower()
        value = os.environ[varname]
        uris[key] = value

    # Parse all authentication info from environment variables
    authns = {}
    for varname in [
        e for e in os.environ if e.startswith(f'{interface}_AUTHENTICATIONS_USERNAME__')
    ]:
        key = varname.split('__')[-1].lower()
        authns.setdefault(key, {})
        username = os.environ[varname]
        password_varname = f'{interface}_AUTHENTICATIONS_PASSWORD__{key.upper()}'
        try:
            password = os.environ[password_varname]
        except KeyError:
            raise RuntimeError(
                f"unconfigured password that pairs with '{varname}'; "
                f"should be in environment variable '{password_varname}'"
            )
        authns[key]['username'] = username
        authns[key]['password'] = password

    return uris, authns


class ACMConfig(object):
    # Read the config from the environment but ensure that there is always a default URI
    # WBIA doesn't currently support authentications but no reason to not use the same function to read
    # the env config.
    ACM_URIS, ACM_AUTHENTICATIONS = get_env_rest_config('ACM')
    if 'default' not in ACM_URIS:
        ACM_URIS['default'] = 'https://sandbox.tier2.dyn.wildme.io'


class EDMConfig(object):
    # Read the config from the environment but ensure that there is always a default URI
    EDM_URIS, EDM_AUTHENTICATIONS = get_env_rest_config('EDM')
    if 'default' not in EDM_URIS:
        EDM_URIS['default'] = 'https://nextgen.dev-wildbook.org/'


class AssetGroupConfig(object):
    GITLAB_REMOTE_URI = os.getenv('GITLAB_REMOTE_URI', 'https://sub.dyn.wildme.io/')
    GIT_PUBLIC_NAME = os.getenv('GIT_PUBLIC_NAME', 'Houston')
    GIT_EMAIL = os.getenv('GIT_EMAIL', 'dev@wildme.org')
    GITLAB_NAMESPACE = os.getenv('GITLAB_NAMESPACE', 'TEST')
    GITLAB_REMOTE_LOGIN_PAT = os.getenv('GITLAB_REMOTE_LOGIN_PAT')


def _parse_elasticsearch_hosts(raw_hosts_line):
    # Ignore None value, allowing the application to fail on usage =/
    hosts = []
    if raw_hosts_line is None:
        raw_hosts_line = ''

    for host in raw_hosts_line.split(','):
        host = host.strip()
        if ':' in host:
            host = dict(zip(['host', 'port'], host.split(':')))
        hosts.append(host)
    return hosts


class ElasticsearchConfig:
    # Elasticsearch host configuration
    # - for multiple hosts use a comma to separate each host
    # - to specify a port use a colon and port number (e.g. `elasticsearch:9200`)
    ELASTICSEARCH_HOSTS = _parse_elasticsearch_hosts(os.getenv('ELASTICSEARCH_HOSTS'))


class ProductionConfig(
    BaseConfig,
    EDMConfig,
    ACMConfig,
    EmailConfig,
    GoogleConfig,
    AssetGroupConfig,
    ReCaptchaConfig,
    ElasticsearchConfig,
):
    TESTING = False

    BASE_URL = 'https://houston.dyn.wildme.io/'

    MAIL_BASE_URL = BASE_URL
    MAIL_OVERRIDE_RECIPIENTS = None
    MAIL_ERROR_RECIPIENTS = [
        'parham@wildme.org',
    ]

    SENTRY_DSN = 'https://140fc4d010bb43b28417ab57b0e41b44@sentry.dyn.wildme.io/3'


class DevelopmentConfig(
    BaseConfig,
    EDMConfig,
    ACMConfig,
    EmailConfig,
    GoogleConfig,
    AssetGroupConfig,
    ReCaptchaConfig,
    ElasticsearchConfig,
):
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
