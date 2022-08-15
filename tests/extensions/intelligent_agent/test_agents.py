# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import time
from unittest.mock import patch

import pytest
import tweepy

from app.modules.site_settings.models import SiteSetting
from tests.utils import extension_unavailable


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
    tweet.attachments = False
    tweet.data = {}
    return tweet


def set_keys():
    from app.extensions.intelligent_agent.models import TwitterBot

    SiteSetting.set_key_value(TwitterBot.site_setting_id('enabled'), True)
    for req in req_keys:
        SiteSetting.set_key_value(TwitterBot.site_setting_id(req), 'TEST_VALUE')


@pytest.mark.skipif(
    extension_unavailable('intelligent_agent'),
    reason='Intelligent Agent extension disabled',
)
def test_twitter_basics(flask_app):
    from app.extensions.intelligent_agent.models import IntelligentAgent, TwitterBot

    assert not TwitterBot.is_enabled()
    SiteSetting.set_key_value(TwitterBot.site_setting_id('enabled'), True)
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
    assert not IntelligentAgent.get_agent_class_by_short_name('XXXFOOOOOOXXXX')
    assert IntelligentAgent.social_account_key() == 'intelligentagent'
    assert TwitterBot.site_setting_id_short('intelligent_agent_twitterbot_foo') == 'foo'


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
        SiteSetting.set_key_value(TwitterBot.site_setting_id('enabled'), False)
        assert not tb.is_ready()
        res = tb.test_setup()
        assert not res.get('success')
        assert res.get('message') == 'Not enabled.'
        SiteSetting.set_key_value(TwitterBot.site_setting_id('enabled'), True)
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
    from app.extensions.intelligent_agent.models import (
        IntelligentAgentContentState,
        TwitterBot,
        TwitterTweet,
    )

    set_keys()
    tb = TwitterBot()
    fake_tweet = Dummy()
    fake_tweet.id = 'FAKE_TWEET_ID'
    with patch.object(tweepy.Client, 'create_tweet', return_value=fake_tweet):
        tweet = tb.create_tweet_direct('text')
        assert tweet

    # now we "send" images (mock)
    media_resp = Dummy()
    media_resp.media_id = 'MEDIA_123'
    with patch.object(tweepy.API, 'media_upload', return_value=media_resp):
        with patch.object(tweepy.API, 'update_status', return_value=fake_tweet):
            tweet = tb.create_tweet_direct('text', media_paths=['/tmp/fake.jpg'])
            assert tweet

    fake_res = Dummy()
    fake_res.data = []
    fake_res.meta = {'newest_id': 123}
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

    # exception during collect()
    with pytest.raises(Exception):
        with patch.object(
            tweepy.client.Client,
            'search_recent_tweets',
            return_value=fake_res,
            side_effect=Exception('ouch'),
        ):
            with patch.object(tweepy.client.Client, 'get_me', return_value=me_value):
                res = tb.collect()
                assert isinstance(res, list)
                assert len(res) == 0


@pytest.mark.skipif(
    extension_unavailable('intelligent_agent'),
    reason='Intelligent Agent extension disabled',
)
def test_linked_tweet_and_misc(researcher_1, flask_app_client, admin_user):
    from app.extensions.intelligent_agent.models import TwitterBot, TwitterTweet
    from app.modules.users.models import User
    from tests.modules.site_settings.resources import utils as setting_utils

    author_id = 'TEST123'
    tweet = get_fake_tweet()
    tweet.author_id = author_id

    researcher_1.link_account(TwitterBot.social_account_key(), {'id': author_id})
    assert researcher_1.linked_accounts == {'twitter': {'id': author_id}}

    u = User.find_by_linked_account(TwitterBot.social_account_key(), author_id)
    assert u == researcher_1
    u = User.find_by_linked_account(TwitterBot.social_account_key(), '__NOT_FOUND__')
    assert not u
    u = User.find_by_linked_account('NO_SUCH_KEY', '__NOT_FOUND__')
    assert not u

    # this uses the HACK user.twitter_username (and not linked accounts)
    #   thus this test should be fixed when hack goes away
    author_username = 'USERNAME123'
    researcher_1.twitter_username = author_username
    tt = TwitterTweet(tweet)
    tt.source = {'author': {'username': author_username}}
    u = tt.find_author_user()
    assert u == researcher_1
    researcher_1.twitter_username = None

    conf_tx = setting_utils.get_some_taxonomy_dict(flask_app_client, admin_user)
    tt.raw_content = {
        'text': 'this is some test',
        'entities': {
            'hashtags': [
                {'tag': 'somethingmeaningless'},
                {'tag': 'ignoremeforsure'},
                # the "z" is for fuzZy
                {'tag': 'z' + conf_tx['scientificName']},
            ]
        },
    }
    tx = tt.derive_taxonomy()
    assert tx
    assert tx.scientificName == conf_tx['scientificName']

    # now lets try to make data from this
    ok, msg = tt.assemble()
    assert not ok
    assert 'at least one image' in msg

    tweet.attachments = True
    # absorbs the error here, makes not images
    tt = TwitterTweet(tweet)
    assert not tt.get_assets()

    mkey = 'MEDIA_KEY'
    media_obj = Dummy()
    media_obj.media_key = mkey
    media_obj.data = {
        'url': 'http://localhost:84/houston/static/images/icon.png',
    }
    tweet.attachments = {
        'media_keys': [mkey],
    }
    rinc = {
        'media': [media_obj],
    }
    tt = TwitterTweet(tweet, rinc)
    # note, we cant seem to actually GET from urls while testing; will have to mock

    # check some validate_and_set_data() directly
    ok, msg = tt.validate_and_set_data()
    assert not ok
    assert 'species as a hashtag' in msg

    meta = tt.generate_asset_group_metadata()
    assert meta
    assert meta.get('transactionId') == tt._transaction_id

    with pytest.raises(ValueError):
        tt.prepare_media_transaction(['fail'])

    with pytest.raises(ValueError):
        tt.prepare_media_transaction([{}])

    tt._transaction_paths = None
    with pytest.raises(AssertionError):
        tt.generate_asset_group_metadata()

    tt._transaction_ids = None
    with pytest.raises(AssertionError):
        tt.generate_asset_group_metadata()

    # cleanup
    researcher_1.linked_accounts = None


@pytest.mark.skipif(
    extension_unavailable('intelligent_agent'),
    reason='Intelligent Agent extension disabled',
)
def test_nlp_date():
    from app.extensions.intelligent_agent.models import TwitterTweet

    tweet = get_fake_tweet()
    tt = TwitterTweet(tweet)

    # right now we do not have ability to test actual NLP, so this falls back to using created_at
    tt.raw_content = {
        'text': 'happened right at 2000-01-02T03:04:05',
        'created_at': '2000-01-02T03:04:05Z',
    }
    cdt = tt.derive_time()
    assert cdt
    assert cdt.isoformat_in_timezone() == '2000-01-02T03:04:05+00:00'


@pytest.mark.skipif(
    extension_unavailable('intelligent_agent'),
    reason='Intelligent Agent extension disabled',
)
def test_duplicate_tweet(db):
    import sqlalchemy

    from app.extensions.intelligent_agent.models import TwitterTweet

    tweet = get_fake_tweet()
    tweet.id = 123456789
    tt = TwitterTweet(tweet)
    with db.session.begin():
        db.session.add(tt)

    t2 = TwitterTweet(tweet)
    try:
        # saving should be blocked by table constraint
        with db.session.begin():
            db.session.add(t2)
    except sqlalchemy.exc.IntegrityError:
        pass
    len(TwitterTweet.query.all()) == 1

    TwitterTweet.query.delete()
