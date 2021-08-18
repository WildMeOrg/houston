# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,wrong-import-position,wrong-import-order
"""
Extensions setup
================

Extensions provide access to common resources of the application.

Please, put new extension instantiations and initializations here.
"""
import re
import uuid  # NOQA
import json  # NOQA
from datetime import datetime  # NOQA
from .logging import Logging

logging = Logging()

from flask_cors import CORS  # NOQA
import flask.json  # NOQA

cross_origin_resource_sharing = CORS()

from .flask_sqlalchemy import SQLAlchemy  # NOQA
from sqlalchemy.ext import mutable  # NOQA
from sqlalchemy.types import TypeDecorator, CHAR  # NOQA
from sqlalchemy.sql import elements  # NOQA
from sqlalchemy.dialects.postgresql import UUID  # NOQA
from sqlalchemy_utils import types as column_types, Timestamp  # NOQA

db = SQLAlchemy()

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

marshmallow = Marshmallow()

from .auth import OAuth2Provider  # NOQA

oauth2 = OAuth2Provider()

from .email import mail  # NOQA

# from flask_minify import minify  # NOQA

from . import edm  # NOQA

from . import elasticsearch  # NOQA

from . import acm  # NOQA

from . import gitlab  # NOQA

from . import tus  # NOQA

from . import api  # NOQA

from . import config  # NOQA

from . import sentry  # NOQA

from . import stripe  # NOQA

##########################################################################################


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


class TimestampViewed(Timestamp):
    """Adds `viewed` column to a derived declarative model."""

    viewed = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def view(self):
        self.viewed = datetime.utcnow()


class GhostModel(object):
    """
    A completely transient model that allows for Houston to wrap EDM or ACM
    responses into a model and allows for serialization of results with
    Rest-PLUS.

    REST API Read Access : YES
    Houston Exists Check : NO
    Houston Read Access  : NO
    """


class FeatherModel(GhostModel, TimestampViewed):
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

    def is_public(self):
        return False


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


def parallel(worker_func, args_list, kwargs_list=None, thread=True, workers=None):
    from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
    import multiprocessing
    import tqdm

    args_list = list(args_list)

    if workers is None:
        workers = multiprocessing.cpu_count()

    if kwargs_list is None:
        kwargs_list = [{}] * len(args_list)

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


def init_app(app):
    """
    Application extensions initialization.
    """
    global _CONFIG_PATH_CHOICES
    _CONFIG_PATH_CHOICES = sorted(app.config.keys())

    extensions = (
        # The extensions in this block need to remain in this order for proper setup
        logging,
        sentry,
        db,
        api,
        config,
        oauth2,
        login_manager,
        # The remaining extensions
        cross_origin_resource_sharing,
        marshmallow,
        edm,
        elasticsearch,
        acm,
        gitlab,
        tus,
        mail,
        stripe,
    )
    for extension in extensions:
        extension.init_app(app)

    # minify(app=app)

    paranoid = Paranoid(app)
    paranoid.redirect_view = '/'
