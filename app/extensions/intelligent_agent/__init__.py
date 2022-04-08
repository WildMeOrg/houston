# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Base Intelligent Agent

"""
import logging
import uuid

# from flask import current_app, request, session, render_template  # NOQA
# from flask_login import current_user  # NOQA
from app.extensions import db

# from app.utils import HoustonException

from app.extensions import HoustonModel

# import app.extensions.logging as AuditLog  # NOQA
# from app.modules.users.models import User


import app.extensions.logging as AuditLog  # NOQA

#   tweepy


log = logging.getLogger(__name__)


class IntelligentAgent:
    """
    Intelligent Agent base class
    """

    def __init__(self, *args, **kwargs):
        log.warning(f'enabled? {self.is_enabled()}')
        log.warning(f'><><><><><><><><>< INIT {self}')

    def collect(self):
        raise NotImplementedError('collect() must be overridden')

    def test_setup(self):
        log.warning('test_setup() must be overridden')
        return {'success': False}

    # appends necessary site-setting configs for intelligent agents
    @classmethod
    def site_setting_config_all(cls):
        config = {}
        for agent_cls in cls.get_agent_classes():
            config.update(agent_cls.site_setting_config())
        return config

    @classmethod
    def site_setting_config(cls):
        # every agent class needs the enabled setting
        return {
            cls.site_setting_id('enabled'): {
                'type': str,
                'default': None,
                'public': False,
                'edm_definition': {
                    'defaultValue': 'false',
                    'displayType': 'select',
                    'schema': {
                        'choices': [
                            {'label': 'Disabled', 'value': 'false'},
                            {'label': 'Enabled', 'value': 'true'},
                        ]
                    },
                },
            }
        }

    @classmethod
    def short_name(cls):
        return cls.__name__.lower()

    @classmethod
    def site_setting_id(cls, setting):
        return f'intelligent_agent_{cls.short_name()}_{setting}'

    # utility function that does the reverse of the above (trims off prefix)
    @classmethod
    def site_setting_id_short(cls, full_setting):
        prefix = f'intelligent_agent_{cls.short_name()}_'
        if full_setting.startswith(prefix):
            return full_setting[len(prefix) :]
        return full_setting

    @classmethod
    def get_site_setting_value(cls, setting):
        from app.modules.site_settings.models import SiteSetting

        return SiteSetting.get_value(cls.site_setting_id(setting))

    @classmethod
    def get_all_setting_values(cls):
        settings = {}
        for full_key in cls.site_setting_config():
            key = cls.site_setting_id_short(full_key)
            settings[key] = cls.get_site_setting_value(key)
        return settings

    @classmethod
    def is_enabled(cls):
        val = cls.get_site_setting_value('enabled')
        return bool(val and val.lower().startswith('t'))

    @classmethod
    def is_ready(cls):
        return cls.is_enabled()

    @classmethod
    def get_agent_classes(cls):
        from app.extensions.intelligent_agent.models import TwitterBot, DummyTest

        return [
            TwitterBot,
            DummyTest,
        ]


class IntelligentAgentContent(db.Model, HoustonModel):
    """
    Intelligent Agent content (tweet, video, post, etc)
    """

    AGENT_CLASS = IntelligentAgent

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    agent_type = db.Column(db.String(length=128), index=True)

    source = db.Column(db.JSON, default=lambda: {}, nullable=False)

    raw_content = db.Column(db.JSON, default=lambda: {}, nullable=False)

    asset_group_guid = db.Column(
        db.GUID,
        db.ForeignKey('asset_group.guid'),
        index=True,
        nullable=True,
    )
    # asset_group = db.relationship(
    #'AssetGroup',
    # backref=db.backref(
    #'agent_content',
    # primaryjoin='AssetGroup.guid == IntelligentAgentContent.asset_group_guid',
    # order_by='AssetGroup.guid',
    # ),
    # foreign_keys='IntelligentAgentContent.asset_group_guid',
    # )

    def __init__(self, *args, **kwargs):
        self.agent_type = self.AGENT_CLASS.short_name()
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, agent={self.agent_type}'
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def get_assets(self):
        if not self.asset_group_guid:
            return None
        return self.asset_group.assets

    def validate(self):
        pass

    def content_as_string(self):
        return str(self.raw_content)

    def source_as_string(self):
        return str(self.source)
