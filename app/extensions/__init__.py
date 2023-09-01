# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,wrong-import-position,wrong-import-order
"""
Extensions setup
================

Extensions provide access to common resources of the application.

Please, put new extension instantiations and initializations here.
"""
import datetime  # NOQA
import json  # NOQA
import logging as logging_native  # NOQA
import re  # NOQA
import sys  # NOQA
import uuid  # NOQA

import tqdm  # NOQA

from .logging import Logging  # NOQA

logging = Logging()
log = logging_native.getLogger(__name__)  # pylint: disable=invalid-name

import flask.json  # NOQA
import sqlalchemy as sa  # NOQA
from flask_caching import Cache  # NOQA
from flask_executor import Executor  # NOQA
from sqlalchemy.dialects.postgresql import UUID  # NOQA
from sqlalchemy.ext import mutable  # NOQA
from sqlalchemy.sql import elements  # NOQA
from sqlalchemy.types import CHAR, TypeDecorator  # NOQA
from sqlalchemy_utils import types as column_types  # NOQA

from .flask_sqlalchemy import SQLAlchemy  # NOQA

db = SQLAlchemy()

cache = Cache()

executor = Executor()

from sqlalchemy_utils import force_auto_coercion  # NOQA
from sqlalchemy_utils import force_instant_defaults  # NOQA

force_auto_coercion()
force_instant_defaults()

from flask_login import LoginManager  # NOQA

login_manager = LoginManager()
login_manager.login_view = 'frontend.user_login'
##########################################################################################
# IMPORTANT: Do not uncomment the line below, it will break the oauth login management
#            that is managed by @login_manager.request_loader
# login_manager.session_protection = "strong"
##########################################################################################

from flask_marshmallow import Marshmallow  # NOQA
from flask_paranoid import Paranoid  # NOQA
from marshmallow import Schema, ValidationError, validates_schema  # NOQA

marshmallow = Marshmallow()

from .auth import OAuth2Provider  # NOQA

oauth2 = OAuth2Provider()

# from flask_minify import minify  # NOQA

from flask_restx_patched import extension_required  # NOQA
from flask_restx_patched import is_extension_enabled  # NOQA

from . import api  # NOQA
from . import sentry  # NOQA

if is_extension_enabled('cors'):
    from flask_cors import CORS  # NOQA

    cross_origin_resource_sharing = CORS()
else:
    cross_origin_resource_sharing = None

if is_extension_enabled('tus'):
    from . import tus  # NOQA
else:
    tus = None

if is_extension_enabled('sage'):
    from . import sage  # NOQA
else:
    sage = None

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

if is_extension_enabled('export'):
    from . import export  # NOQA
else:
    export = None

if is_extension_enabled('intelligent_agent'):
    from . import intelligent_agent  # NOQA
else:
    intelligent_agent = None

if is_extension_enabled('mail'):
    from .email import mail  # NOQA
else:
    mail = None

if is_extension_enabled('stripe'):
    from . import stripe  # NOQA
else:
    stripe = None

from . import prometheus  # NOQA


def register_prometheus_model(*args, **kwargs):
    return prometheus.register_prometheus_model(*args, **kwargs)


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
        if isinstance(original_data, list):
            original_data_keys = set(
                sum((list(data.keys()) for data in original_data), start=[])
            )
        else:
            original_data_keys = set(original_data)
        unknown = original_data_keys - set(valid_fields)
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
                    get_error(errors[key], results, _keys + [str(key)])
                else:
                    if key != '_schema':
                        _keys.append(str(key))
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
                obj[key] = datetime.datetime.strptime(value, '%a, %d %b %Y %H:%M:%S %Z')
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

    created = db.Column(
        db.DateTime, index=True, default=datetime.datetime.utcnow, nullable=False
    )
    updated = db.Column(
        db.DateTime, index=True, default=datetime.datetime.utcnow, nullable=False
    )
    indexed = db.Column(
        db.DateTime, index=True, default=datetime.datetime.utcnow, nullable=False
    )


@sa.event.listens_for(Timestamp, 'before_update', propagate=True)
def timestamp_before_update(mapper, connection, target):
    # When a model with a timestamp is updated; force update the updated
    # timestamp.
    target.updated = datetime.datetime.utcnow()


class TimestampViewed(Timestamp):
    """Adds `viewed` column to a derived declarative model."""

    viewed = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)

    def view(self):
        self.viewed = datetime.datetime.utcnow()


if elasticsearch is None:

    def register_elasticsearch_model(*args, **kwargs):
        pass

    def elasticsearch_context(*args, **kwargs):
        import contextlib

        context = contextlib.nullcontext()
        return context

    class ElasticsearchModel(object):
        elasticsearchable = False
        index_name = None

        def index(self, *args, **kwargs):
            pass

        def elasticsearch(self, *args, **kwargs):
            return []


else:

    def register_elasticsearch_model(*args, **kwargs):
        return elasticsearch.register_elasticsearch_model(*args, **kwargs)

    def elasticsearch_context(*args, **kwargs):
        from app.extensions import elasticsearch as es

        context = es.session.begin(*args, **kwargs)
        return context

    ElasticsearchModel = elasticsearch.ElasticsearchModel


if sage is None:

    class SageModel(object):
        pass


else:

    SageModel = sage.SageModel


class HoustonModel(TimestampViewed, ElasticsearchModel):
    """
    A completely transient model that allows for Houston to wrap EDM or Sage
    responses into a model and allows for serialization of results with
    Rest-PLUS.

    REST API Read Access : YES
    Houston Exists Check : NO
    Houston Read Access  : NO
    """

    @classmethod
    def query_search(cls, search=None, args=None):
        from sqlalchemy import and_, or_

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
        from sqlalchemy import String
        from sqlalchemy_utils.functions import cast_if

        return (cast_if(cls.guid, String).contains(term),)

    @classmethod
    def get_multiple(cls, guids):
        if not guids or not isinstance(guids, list) or len(guids) < 1:
            return []
        return cls.query.filter(cls.guid.in_(guids)).all()

    @property
    def exists(self):
        cls = self.__class__
        return (
            cls.query.filter(cls.guid == self.guid).with_entities(cls.guid).first()
            is not None
        )

    def is_public(self):
        # Assume public if _owned_ by the public user
        if hasattr(self, 'user_is_owner'):
            from app.modules.users.models import User

            return self.user_is_owner(User.get_public_user())
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

    def get_all_owners(self):
        if hasattr(self, 'owner'):
            return [getattr(self, 'owner')]
        # intentionally owners (plural) before owner(singular) as sighting has both
        if hasattr(self, 'get_owners'):
            return getattr(self, 'get_owners')()
        if hasattr(self, 'get_owner'):
            return [getattr(self, 'get_owner')()]

        return []


class CustomFieldMixin(object):
    """
    Mixin class for any class that has custom fields (e.g. Encounter, Sighting, Individual)
    This factors out code that would be virtually identical for all.
    Class must have the custom fields as a self.custom_fields object that is a json blob
    """

    def set_custom_field_value(self, cfd_id, value):
        from app.modules.site_settings.helpers import SiteSettingCustomFields

        if not SiteSettingCustomFields.is_valid_value_for_class(
            self.__class__.__name__, cfd_id, value
        ):
            log.error(
                f'value "{value}" not valid for customField definition id {cfd_id} (on {self})'
            )
            raise ValueError(
                f'Value "{value}" is not valid for {SiteSettingCustomFields.nice_name(self.__class__.__name__, cfd_id)}'
            )
        cf = self.custom_fields or {}
        cf[cfd_id] = SiteSettingCustomFields.serialize_value(
            self.__class__.__name__, cfd_id, value
        )

        with db.session.begin(subtransactions=True):
            self.custom_fields = cf
            db.session.merge(self)

    # raw=True means return json-value without converting to object type
    def get_custom_field_value(self, cfd_id, raw=False):
        from app.modules.site_settings.helpers import SiteSettingCustomFields

        # check defn exists/valid
        defn = SiteSettingCustomFields.get_definition(self.__class__.__name__, cfd_id)
        assert defn
        cf = self.custom_fields or {}
        raw_value = cf.get(cfd_id)
        if raw:
            return raw_value
        return SiteSettingCustomFields.deserialize_value(defn, raw_value)

    # will set multiple via set_dict:  { cfdId0: value0, ...., cfdIdN: valueN }
    def set_custom_field_values(self, set_dict):
        from app.modules.site_settings.helpers import SiteSettingCustomFields

        assert isinstance(set_dict, dict), 'must pass dict'
        cf = self.custom_fields or {}
        # this will overwrite existing values in self.custom_fields for these cfd_ids
        for cfd_id in set_dict:
            value = set_dict[cfd_id]
            if not SiteSettingCustomFields.is_valid_value_for_class(
                self.__class__.__name__, cfd_id, value
            ):
                log.error(
                    f'value "{value}" not valid for customField definition id {cfd_id} (on {self})'
                )
                raise ValueError(
                    f'Value "{value}" is not valid for {SiteSettingCustomFields.nice_name(self.__class__.__name__, cfd_id)}'
                )
            cf[cfd_id] = SiteSettingCustomFields.serialize_value(
                self.__class__.__name__, cfd_id, value
            )

        with db.session.begin(subtransactions=True):
            self.custom_fields = cf
            db.session.merge(self)

    # does above, but assumes values are serialized, so deserializes first
    def set_custom_field_values_json(self, set_dict):
        from app.modules.site_settings.helpers import SiteSettingCustomFields

        assert isinstance(set_dict, dict), 'must pass dict'
        for cfd_id in set_dict:
            value = set_dict[cfd_id]
            if value is not None:
                defn = SiteSettingCustomFields.get_definition(
                    self.__class__.__name__, cfd_id
                )
                assert defn
                set_dict[cfd_id] = SiteSettingCustomFields.deserialize_value(defn, value)
        self.set_custom_field_values(set_dict)

    def reset_custom_field_value(self, cfd_id):
        from app.modules.site_settings.helpers import SiteSettingCustomFields

        defn = SiteSettingCustomFields.get_definition(self.__class__.__name__, cfd_id)
        if not defn:
            raise ValueError(f'invalid customField definition id {cfd_id}')
        cf = self.custom_fields or {}
        if cfd_id not in cf:
            return
        del cf[cfd_id]
        self.custom_fields = cf

    # TODO we probably want one to ADD values to a multiple=TRUE list-type

    def get_custom_fields_elasticsearch(self):
        from app.modules.site_settings.helpers import SiteSettingCustomFields

        cf = self.custom_fields
        cf_es = {}
        for cfd_id in cf:
            if not SiteSettingCustomFields.is_valid_value_for_class(
                self.__class__.__name__, cfd_id, cf[cfd_id]
            ):
                log.warning(
                    f'skipping custom field definition {cfd_id} with invalid value "{cf[cfd_id]}" on {self}'
                )
            else:
                defn = SiteSettingCustomFields.get_definition(
                    self.__class__.__name__, cfd_id
                )
                val = cf[cfd_id]
                if defn['type'] == 'geo':
                    if (
                        isinstance(val, list)
                        and len(val) == 2
                        and val[0] is not None
                        and val[1] is not None
                    ):
                        val = {'lat': val[0], 'lon': val[1]}
                    else:
                        val = None
                cf_es[cfd_id] = val
        return cf_es

    @classmethod
    def custom_field_elasticsearch_mappings(cls, mapping):
        from app.modules.site_settings.models import SiteSetting

        if not mapping or 'properties' not in mapping:
            return mapping

        es_type_map = {
            'date': 'date',
            'float': 'float',
            'feetmeters': 'float',
            'integer': 'integer',
            'geo': 'geo_point',
            'boolean': 'boolean',
        }
        data = SiteSetting.get_value(f'site.custom.customFields.{cls.__name__}') or {}
        definitions = data.get('definitions', [])
        for defn in definitions:
            es_type = es_type_map.get(defn['type'], 'text')
            mapping['properties'][defn['id']] = {'type': es_type}
        return mapping

    def export_custom_fields(self, data):
        from app.modules.site_settings.helpers import SiteSettingCustomFields

        defns = SiteSettingCustomFields.definitions_by_category(self.__class__.__name__)
        if not len(defns):
            return
        defns = defns[next(iter(defns))]
        cf = self.custom_fields
        for defn in defns:
            val = cf.get(defn['id'])
            # TODO twiddle val for export
            data[f"customField.{defn.get('name', defn['id'])}"] = val


class ExportMixin(object):
    """
    Mixin class for any class that has can be exported
    """

    @property
    def export_data(self):
        data = {}
        data['guid'] = str(self.guid)
        data['created'] = self.created.isoformat()[0:19] + 'Z'
        data['updated'] = self.updated.isoformat()[0:19] + 'Z'
        if hasattr(self, 'time'):
            data['time'] = self.get_time_isoformat_in_timezone()
            data['timeSpecificity'] = self.get_time_specificity().value
        if hasattr(self, 'custom_fields'):
            self.export_custom_fields(data)
        return data


##########################################################################################


mutable.MutableDict.associate_with(JsonEncodedDict)

db.GUID = GUID
db.JSON = JSON


##########################################################################################


def parallel(
    worker_func, args_list, kwargs_list=None, thread=True, workers=None, desc=None
):
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

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


def init_app(app, force_enable=False, force_disable=None):
    """
    Application extensions initialization.
    """
    if force_disable is None:
        force_disable = []

    log = logging_native.getLogger(__name__)

    # The extensions in this block need to remain in this order for proper setup
    essential_extensions = {
        'logging': logging,
        'sentry': sentry,
        'db': db,
        'cache': cache,
        'executor': executor,
        'api': api,
        'oauth2': oauth2,
        'login': login_manager,
        'marshmallow': marshmallow,
        'prometheus': prometheus,
    }

    extension_names = essential_extensions.keys()
    for extension_name in extension_names:
        if extension_name not in force_disable:
            log.info('Init required extension {!r}'.format(extension_name))
            extension = essential_extensions.get(extension_name)
            extension.init_app(app)
        else:
            log.info(
                'Skipped required extension {!r} (force disabled)'.format(extension_name)
            )

    # The remaining extensions
    optional_extensions = {
        'cors': cross_origin_resource_sharing,
        'tus': tus,
        'sage': sage,
        'edm': edm,
        'gitlab': gitlab,
        'elasticsearch': elasticsearch,
        'export': export,
        'intelligent_agent': intelligent_agent,
        'mail': mail,
        'stripe': stripe,
    }
    executor.EXECUTOR_TYPE = app.config['EXECUTOR_TYPE']
    executor.EXECUTOR_MAX_WORKERS = app.config['EXECUTOR_MAX_WORKERS']
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
            log.info('Skipped optional extension {!r} (disabled)'.format(extension_name))
        else:
            log.info(
                'Skipped optional extension {!r} (force disabled)'.format(extension_name)
            )

    # minify(app=app)

    paranoid = Paranoid(app)
    paranoid.redirect_view = '/'
