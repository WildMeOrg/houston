# -*- coding: utf-8 -*-
"""
AssetGroups database models
--------------------
"""
# import copy
# import enum
# from flask import current_app, url_for
# from flask_login import current_user  # NOQA
from datetime import datetime  # NOQA

# from flask_restx_patched._http import HTTPStatus
# from app.extensions import db, HoustonModel
import app.extensions.logging as AuditLog  # NOQA
from app.extensions.intelligent_agent import IntelligentAgent, IntelligentAgentContent
import random

# from app.utils import HoustonException

import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class DummyTest(IntelligentAgent):
    """
    A test intelligent Agent
    """

    def test_setup(self):
        return {'success': True, 'message': 'DummyTest is always ready.'}

    @classmethod
    def site_setting_config(cls):
        return {
            cls.site_setting_id('dummy_secret'): {
                'type': str,
                'default': None,
                'public': False,
            },
            cls.site_setting_id('greeting'): {
                'type': str,
                'default': None,
                'public': False,
            },
        }

    def collect(self):
        return [DummyMessage() for x in range(int(random.random() * 10) + 4)]

    # always on! (for now?)
    @classmethod
    def is_enabled(self):
        return True


class DummyMessage(IntelligentAgentContent):
    AGENT_CLASS = DummyTest

    def __init__(self, *args, **kwargs):
        from app.utils import get_stored_filename

        self.source = {
            'created': datetime.utcnow().isoformat() + '+00:00',
            'author': get_stored_filename(str(random.random())),
        }
        self.raw_content = {
            'content': [
                get_stored_filename(str(random.random())),
                get_stored_filename(str(random.random())),
                get_stored_filename(str(random.random())),
            ]
        }
        super().__init__(*args, **kwargs)

    def content_as_string(self):
        return ' / '.join(self.raw_content['content'])

    def source_as_string(self):
        return f"by {self.source['author']} on {self.source['created']}"


class TwitterBot(IntelligentAgent):
    """
    TwitterBot intelligent Agent
    """

    api = None

    def __init__(self, *args, **kwargs):
        if not self.is_ready():
            raise ValueError('TwitterBot not ready for usage.')
        self.api = self.get_api()
        log.debug(f'TwitterBot() obtained {self.api}')
        super().__init__(*args, **kwargs)

    def test_setup(self):
        if not self.is_enabled():
            return {'success': False, 'message': 'Not enabled.'}
        if not self.is_ready():
            return {'success': False, 'message': 'Not ready.'}
        if not self.api:
            return {'success': False, 'message': 'api unset.'}
        try:
            twitter_settings = self.api.get_settings()
        except Exception as ex:
            log.warning(f'TwitterBot.test_setup() api call got exception: {str(ex)}')
            return {'success': False, 'message': f'api exception: {str(ex)}'}
        assert twitter_settings
        log.debug(
            f'TwitterBot.test_setup() api.get_settings successfully returned: {twitter_settings}'
        )
        return {
            'success': True,
            'message': f"Success: Twitter screen name is '{twitter_settings.get('screen_name', 'UNKNOWN')}'",
            'screen_name': twitter_settings.get('screen_name'),
        }

    # get_settings() [currently] returns:
    # {'allow_contributor_request': 'all',
    #  'allow_dm_groups_from': 'following',
    #  'allow_dms_from': 'following',
    #  'always_use_https': True,
    #  'discoverable_by_email': True,
    #  'discoverable_by_mobile_phone': False,
    #  'display_sensitive_media': False,
    #  'geo_enabled': False,
    #  'language': 'en',
    #  'protected': False,
    #  'screen_name': 'TweetABruce',
    #  'sleep_time': {'enabled': False, 'end_time': None, 'start_time': None},
    #  'translator_type': 'none',
    #  'use_cookie_personalization': False}
    def get_screen_name(self):
        # could possibly set this as a (read-only) SiteSetting so we dont have to hit api every time
        twitter_settings = self.api.get_settings()
        assert twitter_settings
        return twitter_settings.get('screen_name', 'ERROR-SCREEN-NAME')

    @classmethod
    def is_ready(cls):
        if not cls.is_enabled():
            log.info('TwitterBot.is_ready(): agent not enabled.')
            return False
        # this required-field stuff could be generalized to base class with required:True on config?
        settings = cls.get_all_setting_values()
        required = [
            'consumer_key',
            'consumer_secret',
            'access_token',
            'access_token_secret',
        ]
        missing = []
        for key in required:
            if not settings.get(key):
                missing.append(key)
        if missing:
            log.info(f'TwitterBot.is_ready(): required settings missing: {missing}')
            return False
        return True

    @classmethod
    def site_setting_config(cls):
        config = super().site_setting_config()  # gets us the 'enabled' config
        config.update(
            {
                cls.site_setting_id('consumer_key'): {
                    'type': str,
                    'default': None,
                    'public': False,
                },
                cls.site_setting_id('consumer_secret'): {
                    'type': str,
                    'default': None,
                    'public': False,
                },
                cls.site_setting_id('access_token'): {
                    'type': str,
                    'default': None,
                    'public': False,
                },
                cls.site_setting_id('access_token_secret'): {
                    'type': str,
                    'default': None,
                    'public': False,
                },
            }
        )
        return config

    def get_api(self):
        if not self.is_ready():
            raise ValueError('TwitterBot get_api(): not ready for usage.')
        import tweepy

        settings = self.get_all_setting_values()
        auth = tweepy.OAuth1UserHandler(
            settings.get('consumer_key'),
            settings.get('consumer_secret'),
            settings.get('access_token'),
            settings.get('access_token_secret'),
        )
        return tweepy.API(auth)


class TwitterTweet(IntelligentAgentContent):
    AGENT_CLASS = TwitterBot
    pass
