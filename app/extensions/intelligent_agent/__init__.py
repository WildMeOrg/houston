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

    @classmethod
    def start(cls):
        log.info(f'{cls} default start: NOP')
        return None

    @classmethod
    def restart(cls):
        log.info(f'{cls} default restart (calling stop/start)')
        cls.stop()
        return cls.start()

    @classmethod
    def stop(cls):
        log.info(f'{cls} default stop: NOP')
        return None

    @classmethod
    def start_all_agents(cls):
        for agent_cls in cls.get_agent_classes():
            rtn = agent_cls.start()
            log.debug(f'start_all_agents() {agent_cls.short_name()}: {rtn}')

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

    @classmethod
    def set_persisted_value(cls, key, value):
        from app.utils import set_persisted_value

        full_key = f'intelligent_agent_{cls.short_name()}_{key}'
        log.debug(f'set_persisted_value({full_key}, {value})')
        return set_persisted_value(full_key, value)

    @classmethod
    def get_persisted_value(cls, key):
        from app.utils import get_persisted_value

        full_key = f'intelligent_agent_{cls.short_name()}_{key}'
        return get_persisted_value(full_key)


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
        if not self.asset_group:
            return None
        return self.asset_group.assets

    def content_as_string(self):
        return str(self.raw_content)

    def source_as_string(self):
        return str(self.source)

    def find_author_user(self):
        from app.modules.users.models import User

        return User.find_by_linked_account(
            self.AGENT_CLASS.social_account_key(),
            self.get_author_id(),
        )

    # can (should?) be overridden to be agent-specific if desired
    #   used for things like filename prefixes etc, so should be fairly "filename-friendly"
    def id_string(self):
        return self.guid

    def derive_time(self):
        raise NotImplementedError('must be overridden')

    def derive_taxonomy(self):
        raise NotImplementedError('must be overridden')

    def derive_location(self):
        raise NotImplementedError('must be overridden')

    def get_species_detection_models(self):
        # FIXME some magic to derive via taxonomy (on .data)
        return ['african_terrestrial']

    # this validates and sets data, and creates AssetGroup
    #   will return (success, error-message)
    # probably want to use these rather than the pieces below (which are separate
    #   to allow for overriding if needed)
    def assemble(self):
        import traceback

        ok, err = self.validate_and_set_data()
        if not ok:
            return ok, err
        try:
            ag_metadata = self.generate_asset_group_metadata()
        except Exception as ex:
            log.error(
                f'assemble() on {self} had problems generating AssetGroup metadata: {str(ex)}'
            )
            log.debug(traceback.format_exc())
            return False, _('Problem preparing data')
        try:
            self.generate_asset_group(ag_metadata)
        except Exception as ex:
            log.error(
                f'assemble() on {self} had problems generating AssetGroup: {str(ex)}'
            )
            log.debug(traceback.format_exc())
            return False, _('Problem processing images')
        return True, None

    # see assemble()
    def validate_and_set_data(self):
        if not hasattr(self, '_transaction_paths') or not self._transaction_paths:
            return False, _('You must include at least one image.')
        data = {}
        tx = self.derive_taxonomy()
        if not tx:
            return False, _('You must include the species as a hashtag.')
        data['taxonomy_guid'] = tx.guid
        loc = self.derive_location()
        if not loc:
            return False, _('You must include the location ID as a hashtag.')
        data['location_id'] = loc
        cdt = self.derive_time()
        if not cdt:
            return False, _('You must tell us when this occurred.')
        data['time'] = cdt.isoformat_in_timezone()
        data['time_specificity'] = cdt.specificity.value
        data.update(self.data or {})
        self.data = data
        return True, None

    # see assemble()
    # this assumes validate_and_set_data() is run
    def generate_asset_group_metadata(self):
        assert self._transaction_id
        assert self._transaction_paths
        meta = {
            'speciesDetectionModel': self.get_species_detection_models(),
            'uploadType': 'form',
            'description': f'{self.AGENT_CLASS.short_name()}: [{self.guid}] {self.content_as_string()}',
            'transactionId': self._transaction_id,
            'sightings': [
                {
                    'assetReferences': self._transaction_paths,
                    'comments': self.content_as_string(),
                    'speciesDetectionModel': self.get_species_detection_models(),
                    'locationId': self.data.get('location_id'),
                    'taxonomy': self.data.get('taxonomy_guid'),
                    'time': self.data.get('time'),
                    'timeSpecificity': self.data.get('time_specificity'),
                    'encounters': [
                        {
                            'locationId': self.data.get('location_id'),
                            'taxonomy': self.data.get('taxonomy_guid'),
                            'time': self.data.get('time'),
                            'timeSpecificity': self.data.get('time_specificity'),
                        }
                    ],
                }
            ],
        }
        return meta

    # media_data is currently a list of dicts, that must have a url and optionally `id`
    #   this gets them to the transaction dir so they can be used by generate_asset_group
    #   sets self._transaction_paths for this purpose -- which is validated by validate_and_set_data()
    def prepare_media_transaction(self, media_data):
        if not isinstance(media_data, list) or not media_data:
            raise ValueError('invalid or empty media_data')
        import requests
        import uuid
        import os
        from app.extensions.tus import tus_upload_dir, tus_write_file_metadata
        from app.utils import get_stored_filename

        # basically replicate tus transaction dir, to drop files in
        self._transaction_id = str(uuid.uuid4())
        target_dir = tus_upload_dir(current_app, transaction_id=self._transaction_id)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        ct = 0
        self._transaction_paths = []
        for md in media_data:
            if not isinstance(md, dict):
                raise ValueError('media_data element is not a dict')
            url = md.get('url')
            if not url:
                raise ValueError(f'no url in {md}')
            original_filename = f"{self.id_string()}-{md.get('id', 'unknown')}-{ct}"
            self._transaction_paths.append(original_filename)
            target_path = os.path.join(target_dir, get_stored_filename(original_filename))
            log.debug(f'trying get {url} -> {target_path}')
            resp = requests.get(url)
            open(target_path, 'wb').write(resp.content)
            tus_write_file_metadata(target_path, original_filename)
            ct += 1
        log.debug(f'prepare_media_transaction() processed {self._transaction_paths}')
        return self._transaction_paths

    # this has all sorts of exceptions one might get
    def generate_asset_group(self, metadata_json):
        import app.extensions.logging as AuditLog  # NOQA
        from app.extensions.elapsed_time import ElapsedTime
        from app.modules.asset_groups.models import AssetGroup, AssetGroupMetadata

        assert isinstance(metadata_json, dict)
        timer = ElapsedTime()
        metadata = AssetGroupMetadata(metadata_json)
        metadata.process_request()
        metadata.owner = self.owner  # override!
        self.asset_group = AssetGroup.create_from_metadata(metadata)
        # do we always want to do this?
        self.asset_group.begin_ia_pipeline(metadata)
        AuditLog.user_create_object(log, self.asset_group, duration=timer.elapsed())
        return self.asset_group
