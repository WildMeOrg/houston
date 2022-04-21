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
import gettext
import traceback


# from app.utils import HoustonException

import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
_ = gettext.gettext


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
            expansions=['attachments.media_keys', 'author_id'],
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
                self.create_tweet_queued(
                    None,  # FIXME
                    _('We could not process your tweet: ') + str(ex),
                    in_reply_to=None,
                )
                # TODO can we still reply to user without tt?
                continue
            ok, err = tt.validate_and_set_data()
            if ok:
                self.state = IntelligentAgentContentState.active
                tt.respond_to(_('Thank you!  We are processing your tweet.'))
                tweets.append(tt)
            else:
                self.state = IntelligentAgentContentState.rejected
                tt.respond_to(_('Sorry, we cannot process this tweet because: ') + err)
            with db.session.begin():
                db.session.add(tt)
        return tweets

    # this should be used with caution -- use create_tweet_queued() to be safer
    def create_tweet_direct(self, text, in_reply_to=None):
        # FIXME implement
        log.info(f'{self} tweeting [re: {in_reply_to}] >>> {text}')
        # Client.create_tweet(*, direct_message_deep_link=None, for_super_followers_only=None, place_id=None, media_ids=None, media_tagged_user_ids=None, poll_duration_minutes=None, poll_options=None, quote_tweet_id=None, exclude_reply_user_ids=None, in_reply_to_tweet_id=None, reply_settings=None, text=None, user_auth=True)
        return

    # preferred usage (vs create_tweet_direct()) as it will throttle outgoing rate to
    #   hopefully keep twitter guards happy
    def create_tweet_queued(self, text, in_reply_to=None):
        # FIXME implement
        self.create_tweet_direct(text, in_reply_to=in_reply_to)
        return

    @classmethod
    def social_account_key(cls):
        return 'twitter_username'

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
        author_data = {'id': tweet.author_id}
        if 'users' in response_includes and len(response_includes['users']):
            author_data = response_includes['users'][0].data
        self.source = {
            'id': tweet.id,
            'author': author_data,
        }
        self.raw_content = tweet.data
        self.owner = self.find_author_user()

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
                        # so generate_asset_group() can use media_key as media "id"
                        media.data['id'] = media.media_key
                        media_data.append(media.data)
                    else:
                        log.debug(
                            f'{media.media_key} not in attachments on tweet {tweet.id}'
                        )
            try:
                ag = self.generate_asset_group(media_data)
                self.asset_group = ag
            except Exception as ex:
                log.warning(
                    f'failed to generate AssetGroup on tweet {tweet.id}: {str(ex)}'
                )
                log.debug(traceback.format_exc())

    # (Pdb) abc[0].raw_content
    # {'id': '1516841133871038464', 'entities': {'mentions': [{'start': 7, 'end': 19, 'username': 'TweetABruce', 'id': '986683924905521152'}], 'urls': [{'start': 88, 'end': 111, 'url': 'https://t.co/eGDgc8FkVI', 'expanded_url': 'https://twitter.com/CitSciBot/status/1516841133871038464/photo/1', 'display_url': 'pic.twitter.com/eGDgc8FkVI'}], 'hashtags': [{'start': 44, 'end': 51, 'tag': 'grevys'}], 'annotations': [{'start': 82, 'end': 86, 'probability': 0.9708, 'type': 'Place', 'normalized_text': 'kenya'}]}, 'attachments': {'media_keys': ['3_1516841098055802880']}, 'text': 'ugh ok @TweetABruce lemme try some hashtags #grevys from my sighting yesterday in kenya https://t.co/eGDgc8FkVI', 'created_at': '2022-04-20T18:08:02.000Z', 'author_id': '989923960295866368'}

    def id_string(self):
        if self.source:
            return f"tweetmedia-{self.source.get('id', 'unknown')}-{self.guid}"
        return f'tweetmedia-unknown-{self.guid}'

    def get_author_id(self):
        return self.source.get('author', {}).get('id') if self.source else None

    def get_author_username(self):
        return self.source.get('author', {}).get('username') if self.source else None

    def content_as_string(self):
        return self.raw_content.get('text')

    def respond_to(self, text):
        log.debug(f'responding to {self} from {self.get_author_username()}: {text}')
        assert self.source and self.source.get('id')
        tb = TwitterBot()
        tb.create_tweet_queued(text, in_reply_to=self.source.get('id'))

    def hashtag_values(self):
        if not self.raw_content.get('entities') or not isinstance(
            self.raw_content['entities'].get('hashtags'), list
        ):
            return []
        values = []
        for ht in self.raw_content['entities']['hashtags']:
            values.append(ht.get('tag'))
        return values

    def derive_time(self):
        # FIXME real implementation
        from app.modules.complex_date_time.models import ComplexDateTime, Specificities

        return ComplexDateTime.from_data(
            {
                'time': self.raw_content.get('created_at').replace('Z', '+00:00'),
                'timeSpecificity': Specificities.time,
            }
        )

    # these could have a default behavior if not provided.  also they could look thru
    #   *whole* text (word-by-word), not just hashtags
    def derive_taxonomy(self):
        from app.modules.site_settings.models import Taxonomy

        for ht in self.hashtag_values():
            tx = Taxonomy.find_fuzzy(ht)
            log.debug(f'hashtag "{ht}" matched {tx}')
            return tx
        return None

    def derive_location(self):
        # FIXME implement using find_fuzzy on Regions
        return 'not-implemented'
