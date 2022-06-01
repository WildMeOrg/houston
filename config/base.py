# -*- coding: utf-8 -*-
import datetime
import multiprocessing
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


class RedisConfig:
    REDIS_HOST = os.getenv('REDIS_HOST')
    REDIS_PORT = os.getenv('REDIS_PORT', '6379')
    REDIS_USE_SSL = bool(int(os.getenv('REDIS_USE_SSL', 0)))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
    REDIS_DATABASE = os.getenv('REDIS_DATABASE', '1')

    @property
    def REDIS_CONNECTION_STRING(self):
        # See redis-py docs for connection string format
        # https://redis-py.readthedocs.io/en/stable/index.html#redis.Redis.from_url
        # See also https://docs.celeryproject.org/en/master/userguide/configuration.html#redis-backend-settings
        if self.REDIS_USE_SSL:
            proto = 'rediss'
            query_string = '?ssl_cert_reqs=required'
        else:
            proto = 'redis'
            query_string = ''
        host = self.REDIS_HOST
        database = self.REDIS_DATABASE
        port = self.REDIS_PORT
        password_parts = ''
        if self.REDIS_PASSWORD:
            # Include the formating bits in this string, because the password is optional.
            # ':' to indicate it's a password and '@' to separate it from the host'
            password_parts = f':{self.REDIS_PASSWORD}@'

        conn_str = f'{proto}://{password_parts}{host}:{port}/{database}{query_string}'
        return conn_str


class BaseConfig(FlaskConfigOverrides, RedisConfig):
    # This class is expected to be initialized to enable the `@property`
    # based settings. The configuration of this application is divided
    # into variants based on context and environment,
    # we capture these two items at initialization.
    # But please do not use the __init__ for anything else.

    def __init__(self, context, environment):
        # Do not add to this initialization method.
        # If you need a computed value,
        # use the `@property` method decorator.

        self.PROJECT_CONTEXT = context
        self.PROJECT_ENVIRONMENT = environment

    PROJECT_NAME = 'Not Set'

    PROJECT_ROOT = PROJECT_ROOT
    PROJECT_DATABASE_PATH = str(DATA_ROOT)

    USE_RELOADER = os.getenv('USE_RELOADER', 'false').lower() != 'false'

    # Mapping to file type taken from
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types
    ASSET_MIME_TYPE_WHITELIST_EXTENSION = {
        'application/json': 'json',
        'application/ld+json': 'jsonld',
        'application/msword': 'doc',
        'application/octet-stream': 'bin',
        'application/ogg': 'ogx',
        'application/pdf': 'pdf',
        'application/rtf': 'rtf',
        'application/vnd.ms-excel': 'xls',
        'application/vnd.oasis.opendocument.spreadsheet': 'ods',
        'application/vnd.oasis.opendocument.text': 'odt',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
        'application/xml': 'xml',
        'image/bmp': 'bmp',
        'image/gif': 'gif',
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/tiff': 'tif',
        'image/webp': 'webp',
        'text/csv': 'csv',
        'text/javascript': 'js',
        'text/plain': 'txt',
        'text/xml': 'xml',
        'video/mpeg': 'mpeg',
        'video/ogg': 'ogv',
        'video/webm': 'webm',
    }

    # specifically this is where tus "temporary" files go
    UPLOADS_DATABASE_PATH = str(DATA_ROOT / 'uploads')
    UPLOADS_TTL_SECONDS = 60 * 60 * 1
    UPLOADS_GIT_COMMIT = False

    FILEUPLOAD_BASE_PATH = str(DATA_ROOT / 'fileuploads')

    @property
    def SQLALCHEMY_DATABASE_URI(self):
        try:
            uri = os.environ['SQLALCHEMY_DATABASE_URI']
        except KeyError:
            raise RuntimeError('Undefined SQLALCHEMY_DATABASE_URI')
        if not uri:
            raise RuntimeError('Defined but blank database uri')
        return uri

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

    # This is defined by the application's context configuration
    ENABLED_EXTENSIONS = ()

    # This is defined by the application's context configuration
    ENABLED_MODULES = ()

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

    MAX_CONTENT_LENGTH = 30 * 1024 * 1024  # Maximum size of 30MB

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
    DEFAULT_EMAIL_SERVICE = os.getenv('DEFAULT_EMAIL_SERVICE')
    DEFAULT_EMAIL_SERVICE_USERNAME = os.getenv('DEFAULT_EMAIL_SERVICE_USERNAME')
    DEFAULT_EMAIL_SERVICE_PASSWORD = os.getenv('DEFAULT_EMAIL_SERVICE_PASSWORD')

    @property
    def MAIL_DEFAULT_SENDER(self):
        return (
            os.getenv('MAIL_DEFAULT_SENDER_NAME', 'Do Not Reply'),
            os.getenv(
                'MAIL_DEFAULT_SENDER_EMAIL',
                f'do-not-reply@{self.SERVER_NAME.replace("www.", "", 1).split(":")[0]}',
            ),
        )


class ReCaptchaConfig(object):
    RECAPTCHA_SITE_VERIFY_API = os.getenv(
        'RECAPTCHA_SITE_VERIFY_API',
        'https://www.google.com/recaptcha/api/siteverify',
    )
    RECAPTCHA_PUBLIC_KEY = os.getenv('RECAPTCHA_PUBLIC_KEY')
    RECAPTCHA_SECRET_KEY = os.getenv('RECAPTCHA_SECRET_KEY')
    RECAPTCHA_BYPASS = os.getenv('RECAPTCHA_BYPASS', 'XXX')


class StripeConfig(object):
    STRIPE_PUBLIC_KEY = 'pk_test_XXX'
    STRIPE_SECRET_KEY = 'sk_test_XXX'


class GoogleAnalyticsConfig(object):
    GOOGLE_ANALYTICS_TAG = 'G-XXX'


class GoogleMapsConfig(object):
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')


class GoogleConfig(GoogleAnalyticsConfig, GoogleMapsConfig):
    pass


class TransloaditConfig:
    TRANSLOADIT_KEY = os.getenv('TRANSLOADIT_KEY')
    TRANSLOADIT_TEMPLATE_ID = os.getenv('TRANSLOADIT_TEMPLATE_ID')
    TRANSLOADIT_SERVICE = os.getenv('TRANSLOADIT_SERVICE')


class FlatfileConfig:
    FLATFILE_KEY = os.getenv('FLATFILE_KEY')


def get_env_rest_config(interface):
    """Parse Sage/EDM configuration from environment variables"""
    # Parse all uris from environment variables
    uris = {}
    for varname in [
        e for e in os.environ if e.startswith(f'{interface}_AUTHENTICATIONS_URI__')
    ]:
        #: e.g. SAGE_AUTHENTICATIONS_URI__DEFAULT
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


class SageConfig(object):
    # Read the config from the environment but ensure that there is always a default URI
    # Sage doesn't currently support authentications but no reason to not use the same function to read
    # the env config.
    SAGE_URIS, SAGE_AUTHENTICATIONS = get_env_rest_config('SAGE')
    if 'default' not in SAGE_URIS:
        SAGE_URIS['default'] = 'https://sandbox.tier2.dyn.wildme.io'


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

    #: using lowercase so Flask won't pick it up as a legit setting
    default_git_ssh_key_filepath = DATA_ROOT / 'id_ssh_key'

    @property
    def GIT_SSH_KEY_FILEPATH(self):
        # Assuming mixed-in with BaseConfig
        fp = Path(os.getenv('GIT_SSH_KEY_FILEPATH', self.default_git_ssh_key_filepath))
        if self.GIT_SSH_KEY is None:
            # Assume the user knows what they are doing and bail out
            # FIXME: It's possible to get here because parts of the application
            #        needs loaded before all the configuration is available.
            return fp
        # Assume if the file exists, we're all good.
        if not fp.exists():
            with fp.open('w') as fb:
                fb.write(self.GIT_SSH_KEY)
                # Write a newline at the end of the file to avoid
                # `Load key "/data/var/id_ssh_key": invalid format`
                fb.write('\n')
            # Ensure permissions are read-only for the runtime user
            # to avoid `Load key "/data/var/id_ssh_key": bad permissions`
            fp.chmod(0o400)
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
    ELASTICSEARCH_HTTP_AUTH = os.getenv('ELASTICSEARCH_HTTP_AUTH', None)
    ELASTICSEARCH_BUILD_INDEX_ON_STARTUP = bool(
        os.getenv('ELASTICSEARCH_BUILD_INDEX_ON_STARTUP', False)
    )
    ELASTICSEARCH_BLOCKING = bool(os.getenv('ELASTICSEARCH_BLOCKING', False))

    CACHE_TYPE = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 60

    EXECUTOR_TYPE = 'thread'
    EXECUTOR_MAX_WORKERS = multiprocessing.cpu_count()


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
