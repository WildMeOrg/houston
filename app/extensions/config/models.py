# -*- coding: utf-8 -*-
"""
Logging adapter
---------------
"""
import logging
import uuid

from flask import current_app as app
from app.extensions import db, HoustonModel

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class HoustonConfig(db.Model, HoustonModel):
    """
    Configuration database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    key = db.Column(db.String, unique=True, nullable=False)
    value = db.Column(db.JSON, nullable=False)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'key={self.key}, '
            'value={self.value}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @classmethod
    def set(self, key, value):
        assert key in app.config

        with app.config.db(app):
            app.config[key] = value
        assert app.config[key] == value

        current_houston_configs = HoustonConfig.query.filter(
            HoustonConfig.key == key
        ).all()
        assert len(current_houston_configs) == 1
        current_houston_config = current_houston_configs[0]
        assert current_houston_config.key == key
        assert current_houston_config.value == value

    @classmethod
    def forget(self, key):
        assert key in app.config

        with app.config.db(app):
            app.config.forget(key)

        current_houston_configs = HoustonConfig.query.filter(
            HoustonConfig.key == key
        ).all()
        assert len(current_houston_configs) == 0
