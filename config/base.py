# -*- coding: utf-8 -*-
import datetime
import os
import random
import string
from pathlib import Path

import flask
import pytz

HERE = Path.cwd()
PROJECT_ROOT = str(HERE)
DATA_ROOT = Path(os.getenv('DATA_ROOT', HERE / '_db'))


class FlaskConfigOverrides:
    # Override Flask's SERVER_NAME (default: None)
    SERVER_NAME = os.getenv('SERVER_NAME')

    # Override Flask's PREFERRED_URL_SCHEME
    @property
    def PREFERRED_URL_SCHEME(self):
        # Flask default behavior is to set it to 'http'
        scheme = os.getenv('PREFERRED_URL_SCHEME', 'http')
        if scheme not in (
            'http',
            'https',
        ):
            raise RuntimeError(
                f"Invalid scheme, '{scheme}' set for "
                "'PREFERRED_URL_SCHEME', please use a valid scheme"
            )
        return scheme


class BaseConfig(FlaskConfigOverrides):
    # This class is expected to be initialized to enable the `@property`
    # based settings. Because the configuration of this application is divided
    # into variants based on context and environment,
    # we capture these two items at initialization.
    # But please do not use the __init__ for anything else.

    def __init__(self, context, environment):
        # Do not add to this initialization method.
        # If you need a computeded value, use the `@property` method decorator.
        self.PROJECT_CONTEXT = context
        self.PROJECT_ENVIRONMENT = environment

    PROJECT_NAME = 'Codex'
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
    #        File "/code/tasks/codex/db.py", in upgrade: `if os.path.exists(_db_filepath):`
    # SQLALCHEMY_DATABASE_PATH = None
    SQLALCHEMY_DATABASE_PATH = str(DATA_ROOT / 'database.sqlite3')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI') or 'sqlite:///%s' % (
        SQLALCHEMY_DATABASE_PATH
    )

    DEBUG = False
    RESTX_ERROR_404_HELP = False

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
    CONFIG_MODEL = 'zebra'

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

    OAUTH_USER = {
        'email': os.getenv('OAUTH_USER_EMAIL', 'oauth-user@wildme.org'),
        'password': os.getenv(
            'OAUTH_USER_PASSWORD',
            ''.join(
                random.choice(string.ascii_letters + string.digits) for _ in range(20)
            ),
        ),
        'is_internal': True,
        'client_id': os.getenv('OAUTH_CLIENT_ID'),
        'client_secret': os.getenv('OAUTH_CLIENT_SECRET'),
    }


class EmailConfig(object):
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = bool(os.getenv('MAIL_USE_TLS', True))
    MAIL_USE_SSL = bool(os.getenv('MAIL_USE_SSL', False))
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', 'dev@wildme.org')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', 'XXX')
    MAIL_DEFAULT_SENDER = (
        os.getenv('MAIL_DEFAULT_SENDER_NAME', 'Codex Mailbot'),
        os.getenv('MAIL_DEFAULT_SENDER_EMAIL', 'changeme@example.com'),
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
    # FIXME: Note, if you change the SSH key, you should also delete the ssh_id file (see GIT_SSH_KEY_FILEPATH)
    GIT_SSH_KEY = os.getenv('GIT_SSH_KEY')

    @property
    def GIT_SSH_KEY_FILEPATH(self):
        # Assuming mixed-in with BaseConfig
        fp = Path(os.getenv('GIT_SSH_KEY_FILEPATH', DATA_ROOT / 'id_ssh_key'))
        if self.GIT_SSH_KEY is None:
            # Assume the user knows what they are doing and bail out
            # FIXME: It's possible to get here because parts of the application
            #        needs loaded before all the configuration is available.
            return fp
        # Assume if the file exists, we're all good.
        if not fp.exists():
            with fp.open('w') as fb:
                fb.write(self.GIT_SSH_KEY)
        return fp

    @property
    def GIT_SSH_COMMAND(self):
        return f'ssh -i {self.GIT_SSH_KEY_FILEPATH} -o StrictHostKeyChecking=no'


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


class WildbookDatabaseConfig:
    WILDBOOK_DB_USER = os.getenv('WILDBOOK_DB_USER')
    WILDBOOK_DB_PASSWORD = os.getenv('WILDBOOK_DB_PASSWORD')
    WILDBOOK_DB_HOST = os.getenv('WILDBOOK_DB_HOST')
    WILDBOOK_DB_PORT = os.getenv('WILDBOOK_DB_PORT', '5432')
    WILDBOOK_DB_NAME = os.getenv('WILDBOOK_DB_NAME')

    @property
    def WILDBOOK_DB_URI(self):
        user = self.WILDBOOK_DB_USER
        password = self.WILDBOOK_DB_PASSWORD
        host = self.WILDBOOK_DB_HOST
        port = self.WILDBOOK_DB_PORT
        database = self.WILDBOOK_DB_NAME
        return f'postgresql://{user}:{password}@{host}:{port}/{database}'
