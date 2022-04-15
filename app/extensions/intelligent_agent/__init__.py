# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Base Intelligent Agent

"""
import logging
import uuid
import enum
import gettext

from flask import current_app

# from flask_login import current_user  # NOQA
from app.extensions import db

# from app.utils import HoustonException

from app.extensions import HoustonModel

# import app.extensions.logging as AuditLog  # NOQA
# from app.modules.users.models import User


import app.extensions.logging as AuditLog  # NOQA

#   tweepy


log = logging.getLogger(__name__)
_ = gettext.gettext


class IntelligentAgent:
    """
    Intelligent Agent base class
    """

    # def __init__(self, *args, **kwargs):
    # log.debug(f'{self} enabled={self.is_enabled()}')

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

    # probably want to override with something more general, like just 'twitter' etc
    @classmethod
    def social_account_key(cls):
        return cls.short_name()

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

    @classmethod
    def get_agent_class_by_short_name(cls, short_name):
        for agent_cls in cls.get_agent_classes():
            if agent_cls.short_name() == short_name:
                return agent_cls
        return None

    # THESE MAY BE DEPRECATING
    @classmethod
    def full_text_key(cls, short_key):
        return f'intelligent_agent_{cls.short_name()}_{short_key}'

    # this will/should point to a global translation library, but this is
    #  the bottleneck for it now
    @classmethod
    def translate_text(cls, key, vals=None, lang_code='en_US'):
        full_key = cls.full_text_key(key)
        return f'NOT YET IMPLEMENTED key={full_key}'


class IntelligentAgentContentState(str, enum.Enum):
    intake = 'intake'
    rejected = 'rejected'
    active = 'active'
    complete = 'complete'
    error = 'error'


class IntelligentAgentContent(db.Model, HoustonModel):
    """
    Intelligent Agent content (tweet, video, post, etc)
    """

    AGENT_CLASS = IntelligentAgent

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    agent_type = db.Column(db.String(length=128), index=True, nullable=False)
    state = db.Column(
        db.Enum(IntelligentAgentContentState),
        default=IntelligentAgentContentState.intake,
        nullable=False,
        index=True,
    )
    owner_guid = db.Column(
        db.GUID,
        db.ForeignKey('user.guid'),
        index=True,
        nullable=True,
    )
    owner = db.relationship(
        'User',
        foreign_keys=[owner_guid],
    )
    source = db.Column(db.JSON, default=lambda: {}, nullable=False)
    raw_content = db.Column(db.JSON, default=lambda: {}, nullable=False)
    # data derived from raw_content, etc
    data = db.Column(db.JSON, default=lambda: {}, nullable=True)
    asset_group_guid = db.Column(
        db.GUID,
        db.ForeignKey('asset_group.guid'),
        index=True,
        nullable=True,
    )
    asset_group = db.relationship(
        'AssetGroup',
        # backref=db.backref(
        #'agent_content',
        # primaryjoin='AssetGroup.guid == IntelligentAgentContent.asset_group_guid',
        # order_by='AssetGroup.guid',
        # ),
        foreign_keys='IntelligentAgentContent.asset_group_guid',
    )

    def __init__(self, *args, **kwargs):
        self.agent_type = self.AGENT_CLASS.short_name()
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, agent={self.agent_type}'
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def respond_to(self, text_key, text_values=None):
        raise NotImplementedError('respond_to() must be overridden')

    # override
    # this should be what links to User via social_account_key()
    def get_author_id(self):
        return None

    def get_assets(self):
        if not self.asset_group_guid:
            return None
        return self.asset_group.assets

    def content_as_string(self):
        return str(self.raw_content)

    def source_as_string(self):
        return str(self.source)

    def find_author_user(self):
        from app.modules.users.models import User

        return User.find_user_by_social(
            self.AGENT_CLASS.social_account_key(),
            self.get_author_id(),
        )

    def validate(self):
        if not self.get_assets():
            return False, _('You must include at least one image.')
        return True, None

    # can (should?) be overridden to be agent-specific if desired
    #   used for things like filename prefixes etc, so should be fairly "filename-friendly"
    def id_string(self):
        return self.guid

    # media_data is currently a list of dicts, that must have a url and optionally `id`
    #   likely this will be expanded later?
    def generate_asset_group(self, media_data):
        if not isinstance(media_data, list) or not media_data:
            raise ValueError('invalid or empty media_data')
        import requests
        import uuid
        import os
        from app.extensions.tus import tus_upload_dir

        # basically replicate tus transaction dir, to drop files in
        tid = uuid.uuid4()
        target_dir = tus_upload_dir(current_app, transaction_id=str(tid))
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        ct = 0
        for md in media_data:
            if not isinstance(md, dict):
                raise ValueError('media_data element is not a dict')
            url = md.get('url')
            if not url:
                raise ValueError(f'no url in {md}')
            target_filename = f"{self.id_string()}-{md.get('id', 'unknown')}-{ct}"
            target_path = os.path.join(target_dir, target_filename)
            log.debug(f'trying get {url} -> {target_path}')
            resp = requests.get(url)
            open(target_path, 'wb').write(resp.content)
            ct += 1
        return None
