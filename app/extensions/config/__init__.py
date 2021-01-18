# -*- coding: utf-8 -*-
"""
Logging adapter
---------------
"""
import flask
from flask import request
import logging
from functools import partial
import sqlalchemy

from app.extensions.api import api_v1

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class HoustonFlaskConfigContext(object):
    def __init__(self, houston_flask_config, app=None):
        self.houston_flask_config = houston_flask_config
        self.app = app

    def __enter__(self):
        self.houston_flask_config.db_update = True
        self.houston_flask_config.db_app = self.app

    def __exit__(self, type, value, traceback):
        self.houston_flask_config.db_update = False
        self.houston_flask_config.db_app = None


class HoustonFlaskConfig(flask.Config):
    """
    This is a helper extension, which adjusts logging configuration for the
    application.
    """

    USE_UPDATE_OR_INSERT = True

    def __init__(self, *args, **kwargs):
        super(HoustonFlaskConfig, self).__init__(*args, **kwargs)
        self.db_init = False
        self.db_update = False
        self.db_app = None

        self.db = partial(HoustonFlaskConfigContext, self)

    def initialize(self, app):
        assert isinstance(app.config, HoustonFlaskConfig)
        assert not self.db_init
        try:
            self.sync(app)
        except sqlalchemy.exc.OperationalError:
            log.warning(
                'Database is too old to support HoustonFlaskConfig, please update'
            )
        self.db_init = True

    def sync(self, app):
        from .models import HoustonConfig

        # from app.extensions import db as app_db

        assert not self.db_init

        context = None
        if not request:
            context = app.app_context()
            context.push()

        houston_configs = HoustonConfig.query.all()

        if context is not None:
            context.pop()

        for houston_config in houston_configs:
            log.warning('CONFIG DB OVERRIDE: %r' % (houston_config,))
            self[houston_config.key] = houston_config.value

    def __setitem__(self, *args, **kwargs):
        if self.db_update:
            self._set(*args)
        return super(HoustonFlaskConfig, self).__setitem__(*args, **kwargs)

    def __delitem__(self, *args, **kwargs):
        if self.db_update:
            self._delete(*args)
        return super(HoustonFlaskConfig, self).__delitem__(*args, **kwargs)

    def _set(self, key, value):
        from .models import HoustonConfig
        from app.extensions import db as app_db

        assert self.db_init

        app = self.db_app
        if app is None:
            from flask import current_app

            app = current_app

        context = None
        if not request:
            context = app.app_context()
            context.push()

        with app_db.session.begin():
            houston_config = HoustonConfig.query.filter(HoustonConfig.key == key).first()
            if houston_config is None:
                houston_config = HoustonConfig(key=key, value=value)
                app_db.session.add(houston_config)
                label = 'Added'
            else:
                if self.USE_UPDATE_OR_INSERT:
                    if value != houston_config.value:
                        houston_config.value = value
                        app_db.session.merge(houston_config)
                        label = 'Updated'
                    else:
                        label = 'Checked'
                else:
                    raise ValueError(
                        'You tried to update a database config that already exists (use update_or_insert=True)'
                    )
        app_db.session.refresh(houston_config)
        log.warning(
            '%s non-volatile database configuration %r'
            % (
                label,
                houston_config,
            )
        )

        if context is not None:
            context.pop()

    def forget(self, key):
        from .models import HoustonConfig
        from app.extensions import db as app_db

        assert self.db_init

        app = self.db_app
        if app is None:
            from flask import current_app

            app = current_app

        with app.app_context():
            with app_db.session.begin():
                houston_config = HoustonConfig.query.filter(
                    HoustonConfig.key == key
                ).first()
                if houston_config is None:
                    label = 'Skipped'
                else:
                    app_db.session.delete(houston_config)
                    label = 'Deleted'
            log.warning(
                '%s non-volatile database configuration for key %r'
                % (
                    label,
                    key,
                )
            )


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    Config extension initialization point.
    """
    api_v1.add_oauth_scope(
        'config.houston:read', 'Provide access to database configurations'
    )
    api_v1.add_oauth_scope(
        'config.houston:write', 'Provide write access to database configurations'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    app.config.initialize(app)
