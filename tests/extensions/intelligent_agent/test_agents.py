# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

# import uuid
import pytest

# from unittest import mock

from tests.utils import extension_unavailable

# from app.extensions.intelligent_agent import IntelligentAgent, IntelligentAgentContent
from app.modules.site_settings.models import SiteSetting
from app.extensions.intelligent_agent.models import TwitterBot


@pytest.mark.skipif(
    extension_unavailable('intelligent_agent'),
    reason='Intelligent Agent extension disabled',
)
def test_twitter_basics(flask_app):
    assert not TwitterBot.is_enabled()
    SiteSetting.set(TwitterBot.site_setting_id('enabled'), string='true')
    assert TwitterBot.is_enabled()
    assert not TwitterBot.is_ready()

    for req in [
        'consumer_key',
        'consumer_secret',
        'access_token',
        'access_token_secret',
        'bearer_token',
    ]:
        SiteSetting.set(TwitterBot.site_setting_id(req), string='TEST_VALUE')
    assert TwitterBot.is_ready()
    tb = TwitterBot()
    # note: tb.api should be defined now; but would be unusable due to bad values above
    #   to avoid irritating Twitter API, no actual testing is performed against this tb.api
    assert tb.api
