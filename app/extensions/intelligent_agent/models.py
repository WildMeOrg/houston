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
from app.extensions import db
import app.extensions.logging as AuditLog  # NOQA
from app.extensions.intelligent_agent import (
    IntelligentAgent,
    IntelligentAgentContent,
    IntelligentAgentContentState,
)
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
        self.state = IntelligentAgentContentState.complete
        super().__init__(*args, **kwargs)

    def respond_to(self, message):
        log.info(f'responding to {self}: {message}')

    def content_as_string(self):
        return ' / '.join(self.raw_content['content'])

    def source_as_string(self):
        return f"by {self.source['author']} on {self.source['created']}"


class TwitterBot(IntelligentAgent):
    """
    TwitterBot intelligent Agent
    """

    # note, `api` is for V1 Twitter API and `client` if for V2; we obtain both, but probably should
    #   only use V2 unless we have no choice. i think?  more notes at get_api() and get_client()
    api = None
    client = None

    def __init__(self, *args, **kwargs):
        if not self.is_ready():
            raise ValueError('TwitterBot not ready for usage.')
        self.api = self.get_api()
        self.client = self.get_client()
        log.debug(f'TwitterBot() obtained {self.api} and {self.client}')
        super().__init__(*args, **kwargs)

    # this is uses only V2 calls
    def test_setup(self):
        if not self.is_enabled():
            return {'success': False, 'message': 'Not enabled.'}
        if not self.is_ready():
            return {'success': False, 'message': 'Not ready.'}
        if not self.client:
            return {'success': False, 'message': 'client unset.'}
        try:
            # twitter_settings = self.api.get_settings()
            me_data = self.client.get_me()
            assert me_data
            assert me_data.data
            assert me_data.data.username
        except Exception as ex:
            log.warning(f'TwitterBot.test_setup() client call got exception: {str(ex)}')
            return {'success': False, 'message': f'client exception: {str(ex)}'}
        log.debug(
            f'TwitterBot.test_setup() client.get_me() successfully returned: {me_data.data}'
        )
        return {
            'success': True,
            'message': f"Success: Twitter username is '{me_data.data.username}', name is '{me_data.data.name}'.",
            'username': me_data.data.username,
            'name': me_data.data.name,
        }

    def collect(self, since=None):
        assert self.client
        query = self.search_string()
        res = self.client.search_recent_tweets(
            query,
            start_time=since,
            tweet_fields=['created_at', 'author_id', 'entities', 'attachments'],
            expansions=['attachments.media_keys'],
            media_fields=['url', 'height', 'width', 'alt_text'],
        )
        tweets = []
        if not res.data or len(res.data) < 1:
            log.debug(f'collect() on {self} retrieved no tweets with query "{query}"')
            return tweets
        log.info(
            f'collect() on {self} retrieved {len(res.data)} tweet(s) with query "{query}"'
        )
        for twt in res.data:
            try:
                tt = TwitterTweet(twt, res.includes)
            except Exception as ex:
                log.warning(f'failed to process_tweet for {twt} due to: {str(ex)}')
            ok, err = tt.validate()
            if ok:
                tweets.append(tt)
            else:
                # handle error, tell user etc
                self.state = IntelligentAgentContentState.rejected
            with db.session.begin():
                db.session.add(tt)
        return tweets

    # right now we search tweets for only "@USERNAME" references, but this
    #    could be expanded to include some site-setting customizations
    def search_string(self):
        return f'@{self.get_username()}'

    def get_username(self):
        # could possibly set this as a (read-only) SiteSetting so we dont have to hit api every time
        assert self.client
        me_data = self.client.get_me()
        assert me_data
        assert me_data.data
        return me_data.data.username

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
            'bearer_token',
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
                cls.site_setting_id('bearer_token'): {
                    'type': str,
                    'default': None,
                    'public': False,
                },
            }
        )
        return config

    # uses Twitter API v1
    # https://docs.tweepy.org/en/latest/api.html
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

    # preferred(?) Twitter API v2 Client
    # https://docs.tweepy.org/en/latest/client.html
    def get_client(self):
        if not self.is_ready():
            raise ValueError('TwitterBot get_api(): not ready for usage.')
        import tweepy

        settings = self.get_all_setting_values()
        return tweepy.Client(
            settings.get('bearer_token'),
            settings.get('consumer_key'),
            settings.get('consumer_secret'),
            settings.get('access_token'),
            settings.get('access_token_secret'),
        )


class TwitterTweet(IntelligentAgentContent):
    AGENT_CLASS = TwitterBot

    # https://docs.tweepy.org/en/latest/v2_models.html#tweet
    def __init__(self, tweet=None, response_includes=None, *args, **kwargs):
        # from app.utils import get_stored_filename
        super().__init__(*args, **kwargs)
        if not tweet:
            return
        self._tweet = tweet
        self._resinc = response_includes
        self.source = {
            'id': tweet.id,
            'author_id': tweet.author_id,
        }
        self.raw_content = tweet.data
        if tweet.attachments:
            media_data = []
            if not response_includes:
                log.error(f'attachments with no response_includes: tweet {tweet.id}')
            elif 'media' not in response_includes or not response_includes['media']:
                log.error(
                    f'attachments with no media in response_includes: tweet {tweet.id}'
                )
            elif 'media_keys' not in tweet.attachments:
                log.error(f'attachments with no media_keys: tweet {tweet.id}')
            else:  # try to map attachments to media
                for media in response_includes['media']:
                    if media.media_key in tweet.attachments['media_keys']:
                        log.debug(
                            f'{media.media_key} FOUND in attachments on tweet {tweet.id}: {media.data}'
                        )
                        media_data.append(media.data)
                    else:
                        log.debug(
                            f'{media.media_key} not in attachments on tweet {tweet.id}'
                        )
            try:
                ag = TwitterBot.generate_asset_group(media_data)
                self.asset_group = ag
            except Exception as ex:
                log.warning(
                    f'failed to generate AssetGroup on tweet {tweet.id}: {str(ex)}'
                )

    def validate(self):
        return True, None

    def respond_to(self, text_key, text_values=None):
        # TODO make this duh
        pass

    # def has_media
