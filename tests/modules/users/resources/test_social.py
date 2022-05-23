# -*- coding: utf-8 -*-
from unittest import mock

import pytest

from tests.utils import extension_unavailable


@pytest.mark.skipif(
    extension_unavailable('intelligent_agent'),
    reason='IntelligentAgent extension disabled',
)
def test_social_auth_redirect_twitter(flask_app_client, researcher_1, request):
    tweepy_patch = mock.patch('tweepy.OAuth1UserHandler')
    tweepy_handler = tweepy_patch.start()
    request.addfinalizer(tweepy_patch.stop)
    auth = mock.Mock(request_token='12345')
    auth.get_authorization_url.return_value = 'http://example.org/authorization/'
    tweepy_handler.return_value = auth

    twitterbot_patch = mock.patch('app.extensions.intelligent_agent.models.TwitterBot')
    TwitterBot = twitterbot_patch.start()
    request.addfinalizer(twitterbot_patch.stop)
    TwitterBot.get_site_setting_value.side_effect = lambda key: {
        'consumer_key': 'twitter_consumer_key',
        'consumer_secret': 'twitter_consumer_secret',
    }.get(key)

    with flask_app_client.login(researcher_1):
        response = flask_app_client.get('/api/v1/users/social_auth_redirect/twitter')
        assert response.status_code == 302
        assert response.headers['Location'] == 'http://example.org/authorization/'
        assert tweepy_handler.called
        assert tweepy_handler.call_args == mock.call(
            'twitter_consumer_key',
            'twitter_consumer_secret',
            callback='http://localhost:84/api/v1/users/social_callback/twitter',
        )
