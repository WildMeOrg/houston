# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging

import pytest

import tests.modules.account_requests.resources.utils as req_utils
from tests.utils import module_unavailable

log = logging.getLogger(__name__)


@pytest.mark.skipif(
    module_unavailable('account_requests'), reason='AccountRequest module disabled'
)
def test_create(
    flask_app_client,
):
    from app.modules.account_requests.models import AccountRequest

    data = {
        'name': None,
        'email': 'test@example.com',
    }
    result = req_utils.create_account_request(
        flask_app_client, data, expected_status_code=422
    )
    assert 'messages' in result.json
    assert 'name' in result.json['messages']
    assert 'may not be null' in result.json['messages']['name'][0]

    data['name'] = 'has a name now'
    result = req_utils.create_account_request(flask_app_client, data)
    assert result.json['name'] == data['name']
    assert result.json['email'] == data['email']
    AccountRequest.query.delete()


@pytest.mark.skipif(
    module_unavailable('account_requests'), reason='AccountRequest module disabled'
)
def test_read_all(flask_app_client, staff_user, regular_user):
    from app.modules.account_requests.models import AccountRequest

    data = {
        'name': 'test name',
        'email': 'test@example.com',
    }
    req_utils.create_account_request(flask_app_client, data)
    reqs = req_utils.read_all_account_requests(
        flask_app_client, regular_user, expected_status_code=403
    )
    reqs = req_utils.read_all_account_requests(flask_app_client, staff_user)
    test = reqs.json.pop()
    assert test['name'] == data['name']
    assert test['email'] == data['email']
    AccountRequest.query.delete()
