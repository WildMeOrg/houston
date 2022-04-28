# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import pytest

from unittest.mock import patch
from tests.utils import extension_unavailable
import tweepy
import time

# from app.extensions.intelligent_agent import IntelligentAgent, IntelligentAgentContent
from app.modules.site_settings.models import SiteSetting


# manipulate into whatever fake twitter response we want
class Dummy(object):
    pass


req_keys = [
    'consumer_key',
    'consumer_secret',
    'access_token',
    'access_token_secret',
    'bearer_token',
]


def get_fake_tweet():
    tweet = Dummy()
    tweet.id = time.time()
    tweet.author_id = 'author'
    tweet.data = {}
    return tweet


def set_keys():
    from app.extensions.intelligent_agent.models import TwitterBot

    SiteSetting.set(TwitterBot.site_setting_id('enabled'), string='true')
    for req in req_keys:
        SiteSetting.set(TwitterBot.site_setting_id(req), string='TEST_VALUE')


@pytest.mark.skipif(
    extension_unavailable('intelligent_agent'),
    reason='Intelligent Agent extension disabled',
)
def test_twitter_basics(flask_app):
    from app.extensions.intelligent_agent import IntelligentAgent
    from app.extensions.intelligent_agent.models import TwitterBot

    assert not TwitterBot.is_enabled()
    SiteSetting.set(TwitterBot.site_setting_id('enabled'), string='true')
    assert TwitterBot.is_enabled()
    assert not TwitterBot.is_ready()

    set_keys()
    assert TwitterBot.is_ready()
    tb = TwitterBot()
    # note: tb.api should be defined now; but would be unusable due to bad values above
    #   to avoid irritating Twitter API, no actual testing is performed against this tb.api
    assert tb.api

    assert tb.short_name() == 'twitterbot'
    assert tb.get_site_setting_value('consumer_key') == 'TEST_VALUE'
    settings = tb.get_all_setting_values()
    assert set(settings.keys()) >= set(req_keys)

    assert IntelligentAgent.get_agent_class_by_short_name('twitterbot') == TwitterBot


@pytest.mark.skipif(
    extension_unavailable('intelligent_agent'),
    reason='Intelligent Agent extension disabled',
)
def test_twitter_connectivity(flask_app_client):
    from app.extensions.intelligent_agent.models import TwitterBot

    set_keys()
    tb = TwitterBot()

    me_value = Dummy()
    me_value.data = Dummy()
    me_value.data.username = 'A'
    me_value.data.name = 'B'

    with patch.object(tweepy.Client, 'get_me', return_value=me_value):
        SiteSetting.set(TwitterBot.site_setting_id('enabled'), string='false')
        assert not tb.is_ready()
        res = tb.test_setup()
        assert not res.get('success')
        assert res.get('message') == 'Not enabled.'
        SiteSetting.set(TwitterBot.site_setting_id('enabled'), string='true')
        res = tb.test_setup()
        assert res.get('success')
        assert res.get('username') == 'A'
        assert res.get('name') == 'B'

    with patch.object(
        tweepy.Client, 'get_me', return_value=me_value, side_effect=Exception('denied!')
    ):
        res = tb.test_setup()
        assert not res.get('success')
        assert 'exception' in res.get('message')


@pytest.mark.skipif(
    extension_unavailable('intelligent_agent'),
    reason='Intelligent Agent extension disabled',
)
def test_twitter_tweet_io(flask_app_client):
    from app.extensions.intelligent_agent import IntelligentAgentContentState
    from app.extensions.intelligent_agent.models import TwitterBot, TwitterTweet

    set_keys()
    tb = TwitterBot()
    fake_tweet = Dummy()
    fake_tweet.id = 'FAKE_TWEET_ID'
    with patch.object(tweepy.Client, 'create_tweet', return_value=fake_tweet):
        tweet = tb.create_tweet_direct('text')
        # uncomment this line when tweeting is not disabled
        # assert tweet

    fake_res = Dummy()
    fake_res.data = []
    me_value = Dummy()
    me_value.data = Dummy()
    me_value.data.username = 'A'
    me_value.data.name = 'B'

    # collect no tweets
    with patch.object(
        tweepy.client.Client, 'search_recent_tweets', return_value=fake_res
    ):
        with patch.object(tweepy.client.Client, 'get_me', return_value=me_value):
            res = tb.collect()
            assert isinstance(res, list)
            assert len(res) == 0

    # one tweet no image
    tweet = get_fake_tweet()
    tweet.attachments = False
    fake_res.data.append(tweet)
    fake_res.includes = []
    with patch.object(
        tweepy.client.Client, 'search_recent_tweets', return_value=fake_res
    ):
        with patch.object(tweepy.client.Client, 'get_me', return_value=me_value):
            res = tb.collect()
            assert isinstance(res, list)
            assert len(res) == 0
    failed = TwitterTweet.query.first()
    assert failed
    assert failed.state == IntelligentAgentContentState.rejected
