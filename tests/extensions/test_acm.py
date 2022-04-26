# -*- coding: utf-8 -*-
from unittest import mock

import pytest

from tests.utils import extension_unavailable


@pytest.mark.skipif(extension_unavailable('acm'), reason='ACM extension disabled')
def test_https_url_redirect(flask_app):
    # Even if acm responds with a redirect to http url, force it to be
    # https instead
    flask_app.acm._ensure_initialized()
    mock_308 = mock.Mock(
        status_code=308,
        is_redirect=True,
        headers={'location': 'http://acm:5000/api/'},
    )
    mock_200 = mock.Mock(
        status_code=200,
        is_redirect=False,
        ok=True,
        text='{"ok": true}',
    )
    flask_app.acm.uris['default'] = 'https://acm:5000/'

    def mock_post(url, *args, call_count=[], **kwargs):
        if not call_count:
            call_count.append(1)
            return mock_308
        return mock_200

    with mock.patch.object(
        flask_app.acm.sessions['default'], 'post', side_effect=mock_post
    ) as acm_post:
        flask_app.acm._request(
            'post',
            'job.detect_request',
            'cnn',
            passthrough_kwargs={
                'params': {
                    'endpoint': '/api/engine/detect/cnn/lightnet/',
                    'jobid': '1bab866c-cc2e-4ac3-a7e9-ae400a2922ea',
                },
            },
        )
        assert [call_args[0][0] for call_args in acm_post.call_args_list] == [
            'https://acm:5000/api/engine/detect/cnn',
            # Even if acm wants to redirect us to http://acm:5000/api/,
            # use https://acm:5000/api/
            'https://acm:5000/api/',
        ]
