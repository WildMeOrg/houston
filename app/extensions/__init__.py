# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,wrong-import-position,wrong-import-order
"""
Extensions setup
================

Extensions provide access to common resources of the application.

Please, put new extension instantiations and initializations here.
"""
import re  # NOQA
import sys  # NOQA
import uuid  # NOQA
import json  # NOQA
import tqdm  # NOQA
from datetime import datetime  # NOQA
import logging as logging_native  # NOQA
from .logging import Logging  # NOQA

logging = Logging()

import flask.json  # NOQA

from .flask_sqlalchemy import SQLAlchemy  # NOQA
import sqlalchemy as sa  # NOQA
from sqlalchemy.ext import mutable  # NOQA
from flask_caching import Cache  # NOQA
from sqlalchemy.types import TypeDecorator, CHAR  # NOQA
from sqlalchemy.sql import elements  # NOQA
from sqlalchemy.dialects.postgresql import UUID  # NOQA
from sqlalchemy_utils import types as column_types  # NOQA

db = SQLAlchemy()

cache = Cache()

from sqlalchemy_utils import force_auto_coercion, force_instant_defaults  # NOQA

force_auto_coercion()
force_instant_defaults()

from flask_login import LoginManager  # NOQA

login_manager = LoginManager()
##########################################################################################
# IMPORTANT: Do not uncomment the line below, it will break the oauth login management
#            that is managed by @login_manager.request_loader
# login_manager.session_protection = "strong"
##########################################################################################

from flask_paranoid import Paranoid  # NOQA

from flask_marshmallow import Marshmallow  # NOQA
from marshmallow import Schema, validates_schema, ValidationError  # NOQA

marshmallow = Marshmallow()

from .auth import OAuth2Provider  # NOQA

oauth2 = OAuth2Provider()

# from flask_minify import minify  # NOQA

from . import sentry  # NOQA

from . import api  # NOQA

from . import config  # NOQA

from flask_restx_patched import is_extension_enabled, extension_required  # NOQA

if is_extension_enabled('cors'):
    from flask_cors import CORS  # NOQA

    cross_origin_resource_sharing = CORS()
else:
    cross_origin_resource_sharing = None

if is_extension_enabled('tus'):
    from . import tus  # NOQA
else:
    tus = None

if is_extension_enabled('acm'):
    from . import acm  # NOQA
else:
    acm = None

if is_extension_enabled('edm'):
    from . import edm  # NOQA
else:
    edm = None

if is_extension_enabled('gitlab'):
    from . import gitlab  # NOQA
else:
    gitlab = None

if is_extension_enabled('elasticsearch'):
    from . import elasticsearch  # NOQA
else:
    elasticsearch = None

if is_extension_enabled('mail'):
    from .email import mail  # NOQA
else:
    mail = None

if is_extension_enabled('stripe'):
    from . import stripe  # NOQA
else:
    stripe = None


##########################################################################################


class ExtraValidationSchema(Schema):
    @validates_schema(pass_original=True)
    def validates_schema(self, cleaned_data, original_data):
        """
        This method is called after the built-in validation is done.
        cleaned_data is what is left after validation and original_data
        is the original input.

        Raise validation error if there are extra fields not defined in
        the schema.

        This is necessary because marshmallow (before 3.0.0) just
        ignores extra fields without any validation errors.
        """
        if cleaned_data is None:  # Wrong type given, nothing to validate
            return
        valid_fields = sorted(self.fields.keys())
        unknown = set(original_data) - set(valid_fields)
        if unknown:
            raise ValidationError(
                f'Unknown field(s): {", ".join(unknown)}, options are {", ".join(valid_fields)}.'
            )

    def get_error_message(self, errors):
        """
        Validation errors are like this:

        {
            'all': {
                '_schema': [
                    'Unknown field(s): random, options are email, restAPI'
                ],
                'restAPI': [
                    'Not a valid boolean.'
                ]
            }
        }

        This method turns this into an error message like:

        "all": Unknown field(s): random, options are email, restAPI.
        "all.restAPI": Not a valid boolean.
        """
        error_keys = list(errors.keys())
        if error_keys == ['_schema']:
            return ' '.join(errors['_schema'])

        def get_error(errors, results, _keys=[]):
            # Traverse down the error structure depth first so we can get the
            # actual field name.  For example in the example above, we want
            # "all.restAPI" as the field name.
            for key in errors:
                if isinstance(errors[key], dict):
                    if key == '_schema':
                        get_error(errors[key], results, _keys)
                    get_error(errors[key], results, _keys + [key])
                else:
                    if key != '_schema':
                        _keys.append(key)
                    message = ' '.join(errors[key])
                    if not _keys:
                        results.append(message)
                    else:
                        results.append(f'"{".".join(_keys)}": {message}')

        results = []
        get_error(errors, results)
        return ' '.join(results)


class JsonEncodedDict(db.TypeDecorator):
    """Enables JSON storage by encoding and decoding on the fly."""

    impl = db.Text

    def process_bind_param(self, value, dialect):
        if value is None:
            return '{}'
        else:
            return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return {}
        else:
            return json.loads(value)


SA_JSON = db.JSON


def custom_json_decoder(obj):
    for key, value in obj.items():
        if isinstance(value, str) and re.match(
            '^[A-Z][a-z][a-z], [0-9][0-9] [A-Z][a-z][a-z]', value
        ):
            try:
                obj[key] = datetime.strptime(value, '%a, %d %b %Y %H:%M:%S %Z')
            except ValueError:
                pass
    return obj


class JSON(db.TypeDecorator):
    impl = SA_JSON

    def process_bind_param(self, value, dialect):
        # Adapted from sqlalchemy/sql/sqltypes.py JSON.bind_processor
        def json_serializer(*args, **kwargs):
            return json.dumps(*args, **kwargs, cls=flask.json.JSONEncoder)

        def process(value):
            if value is SA_JSON.NULL:
                value = None
            elif isinstance(value, elements.Null) or (
                value is None and self.none_as_null
            ):
                return None

            return json_serializer(value)

        return process(value)

    def process_result_value(self, value, dialect):
        # Adapted from sqlalchemy/sql/sqltypes.py JSON.result_processor
        def json_deserializer(*args, **kwargs):
            return json.loads(*args, **kwargs, object_hook=custom_json_decoder)

        def process(value):
            if value is None:
                return None
            elif isinstance(value, dict):
                return value
            return json_deserializer(value)

        return process(value)

    def compare_values(self, x, y):
        # This method is used to determine whether a field has changed.
        #
        # This is a problem for lists and dicts because if the user edits the
        # list or dict in place, "x" and "y" are going to be the same and we
        # can't determine whether the field has changed.
        #
        # For example, if self.jobs was {}, then we do:
        # self.jobs['job_id'] = {'some': 'stuff'}
        #
        # compare_values is going to get {'job_id': {'some': 'stuff'}} twice
        # because sqlalchemy is unable to get back the previous value of
        # self.jobs which was {}
        #
        # So we can't determine whether the field has actually changed.  If we
        # return True here, the object does not get saved, so we're going to
        # just always return False
        return False


class GUID(db.TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.

    """

    impl = CHAR

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return '%.32x' % uuid.UUID(value).int
            else:
                # hexstring
                return '%.32x' % value.int

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


class Timestamp(object):
    """Adds `created` and `updated` columns to a derived declarative model.

    The `created` column is handled through a default and the `updated`
    column is handled through a `before_update` event that propagates
    for all derived declarative models.

    Copied from sqlalchemy.utils.Timestamp.py and added the index=True
    ::

    """

    created = db.Column(db.DateTime, index=True, default=datetime.utcnow, nullable=False)
    updated = db.Column(db.DateTime, index=True, default=datetime.utcnow, nullable=False)
    indexed = db.Column(db.DateTime, index=True, default=datetime.utcnow, nullable=False)


@sa.event.listens_for(Timestamp, 'before_update', propagate=True)
def timestamp_before_update(mapper, connection, target):
    # When a model with a timestamp is updated; force update the updated
    # timestamp.

    # We are about to update the timestamp of the object, but first check if the update effects the indexed time
    indexed = target._sa_instance_state.committed_state.get('indexed', None)
    if indexed is None:
        updated = datetime.utcnow()
    else:
        updated = indexed

    target.updated = updated
    target._sa_instance_state.committed_state['updated'] = updated

    if indexed is not None:
        assert indexed == updated
        assert (
            target._sa_instance_state.committed_state['indexed']
            == target._sa_instance_state.committed_state['updated']
        )


class TimestampViewed(Timestamp):
    """Adds `viewed` column to a derived declarative model."""

    viewed = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def view(self):
        self.viewed = datetime.utcnow()


if elasticsearch is None:

    def register_elasticsearch_model(*args, **kwargs):
        pass

    def elasticsearch_context(*args, **kwargs):
        import contextlib

        context = contextlib.nullcontext()
        return context

    class ElasticsearchModel(object):
        pass

else:

    def register_elasticsearch_model(*args, **kwargs):
        return elasticsearch.register_elasticsearch_model(*args, **kwargs)

    def elasticsearch_context(*args, **kwargs):
        from app.extensions import elasticsearch as es

        context = es.session.begin(*args, **kwargs)
        return context

    ElasticsearchModel = elasticsearch.ElasticsearchModel


class GhostModel(object):
    """
    A completely transient model that allows for Houston to wrap EDM or ACM
    responses into a model and allows for serialization of results with
    Rest-PLUS.

    REST API Read Access : YES
    Houston Exists Check : NO
    Houston Read Access  : NO
    """


class FeatherModel(GhostModel, TimestampViewed, ElasticsearchModel):
    """
    A light-weight model that 1) stores critical information concerning security
    and permissions or 2) gives Houston insight on frequently-cached information
    so that it can quickly resolve requests itself without needing to query the
    EDM or ACM.

    A FeatherModel inherits from SQLAlchemy.Model and creates a local SQL* table
    in the local Houston database.  All models in Houston also derive from the
    TimestampViewed class, which is an extension of sqlalchemy_utils.models.Timestamp
    to add an additional `viewed` attribute to complement `created` and`updated`.

    A FeatherModel is required to have external metadata and information that is
    stored in a different component.  In general, FeatherModels must be kept
    up-to-date with their responsible external component (e.g. with a version).

    This external component shall be the "constructor" of new objects, such that
    houston will wait for confirmation/creation of new objects from its external
    component prior to the creation of the corresponding FeatherModel object (which
    will then be built using the provided guid and other properties).

    IMPORTANT: If all of the information for a FeatherModel lives inside
    Houston's database, it should be converted into a HoustonModel.

    REST API Read Access : YES
    Houston Exists Check : YES
    Houston Read Access  : YES
    """

    @classmethod
    def query_search(cls, search=None, args=None):
        from sqlalchemy import or_, and_

        if args is not None:
            search = args.get('search', None)

        if search is not None and len(search) == 0:
            search = None

        if search is not None:
            search = search.strip().replace(',', ' ').split(' ')
            search = [term.strip() for term in search]
            search = [term for term in search if len(term) > 0]

            or_terms = []
            for term in search:
                or_term = or_(*cls.query_search_term_hook(term))
                or_terms.append(or_term)
            query = cls.query.filter(and_(*or_terms))
        else:
            query = cls.query

        return query

    @classmethod
    def query_search_term_hook(cls, term):
        from sqlalchemy_utils.functions import cast_if
        from sqlalchemy import String

        return (cast_if(cls.guid, String).contains(term),)

    @classmethod
    def get_multiple(cls, guids):
        if not guids or not isinstance(guids, list) or len(guids) < 1:
            return []
        return cls.query.filter(cls.guid.in_(guids)).all()

    def is_public(self):
        return False

    def current_user_has_view_permission(self):
        from app.modules.users.permissions.rules import ObjectActionRule
        from app.modules.users.permissions.types import AccessOperation

        rule = ObjectActionRule(obj=self, action=AccessOperation.READ)
        return rule.check()

    def current_user_has_edit_permission(self):
        from app.modules.users.permissions.rules import ObjectActionRule
        from app.modules.users.permissions.types import AccessOperation

        rule = ObjectActionRule(obj=self, action=AccessOperation.WRITE)
        return rule.check()


class HoustonModel(FeatherModel):
    """
    A permanent model that stores information for objects in Houston only.  A
    HoustonModel is a fully-fledged database ORM object that has full CRUD
    support and does not need to interface with an external component for any
    information or metadata.

    REST API Read Access : YES
    Houston Exists Check : YES
    Houston Read Access  : YES
    """


##########################################################################################


mutable.MutableDict.associate_with(JsonEncodedDict)

db.GUID = GUID
db.JSON = JSON


##########################################################################################


def parallel(
    worker_func, args_list, kwargs_list=None, thread=True, workers=None, desc=None
):
    from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
    import multiprocessing

    args_list = list(args_list)

    if workers is None:
        workers = multiprocessing.cpu_count()

    if kwargs_list is None:
        kwargs_list = [{}] * len(args_list)

    if desc is None:
        desc = worker_func.__name__

    executor = ThreadPoolExecutor if thread else ProcessPoolExecutor

    with executor(max_workers=workers) as pool:
        futures, results = [], []

        with tqdm.tqdm(total=len(args_list)) as progress:
            for args, kwargs in zip(args_list, kwargs_list):
                future = pool.submit(worker_func, *args, **kwargs)
                future.add_done_callback(lambda p: progress.update())
                futures.append(future)

        for future in tqdm.tqdm(futures):
            result = future.result()
            results.append(result)

        pool.shutdown(True)

    return results


##########################################################################################


# This global is updated dynamically before the config extension is loaded.
# When the config extension is loaded, it instantiates PatchHoustonConfigParameters,
# which expects the global variable below to be configured correctly for all config keys
_CONFIG_PATH_CHOICES = None


def init_app(app, force_enable=False, force_disable=None):
    """
    Application extensions initialization.
    """
    if force_disable is None:
        force_disable = []

    global _CONFIG_PATH_CHOICES
    _CONFIG_PATH_CHOICES = sorted(app.config.keys())

    log = logging_native.getLogger(__name__)

    # The extensions in this block need to remain in this order for proper setup
    essential_extensions = {
        'logging': logging,
        'sentry': sentry,
        'db': db,
        'cache': cache,
        'api': api,
        'config': config,
        'oauth2': oauth2,
        'login': login_manager,
        'marshmallow': marshmallow,
    }

    extension_names = essential_extensions.keys()
    for extension_name in extension_names:
        if extension_name not in force_disable:
            log.info('Init required extension %r' % (extension_name,))
            extension = essential_extensions.get(extension_name)
            extension.init_app(app)
        else:
            log.info('Skipped required extension %r (force disabled)' % (extension_name,))

    # The remaining extensions
    optional_extensions = {
        'cors': cross_origin_resource_sharing,
        'tus': tus,
        'acm': acm,
        'edm': edm,
        'gitlab': gitlab,
        'elasticsearch': elasticsearch,
        'mail': mail,
        'stripe': stripe,
    }

    enabled_extension_names = app.config['ENABLED_EXTENSIONS']

    extension_names = sorted(optional_extensions.keys())
    for extension_name in extension_names:
        if (force_enable or extension_name in enabled_extension_names) and (
            extension_name not in force_disable
        ):
            if force_enable and extension_name not in enabled_extension_names:
                enable_str = ' (forced)'
            else:
                enable_str = ''
            log.info(
                'Init optional extension %r%s'
                % (
                    extension_name,
                    enable_str,
                )
            )
            extension = optional_extensions.get(extension_name)
            if extension is not None:
                extension.init_app(app)
        elif extension_name not in force_disable:
            log.info('Skipped optional extension %r (disabled)' % (extension_name,))
        else:
            log.info('Skipped optional extension %r (force disabled)' % (extension_name,))

    # minify(app=app)

    paranoid = Paranoid(app)
    paranoid.redirect_view = '/'
