# -*- coding: utf-8 -*-
from unittest import mock

from invoke import MockContext


def test_send(flask_app):
    with mock.patch('app.create_app') as create_app:
        create_app.return_value = flask_app

        from tasks.app.email import send as send_task

        with mock.patch('app.extensions.email.mail.send') as mock_send:
            send_task(MockContext(), 'nobody@example.org', 'test body')
            assert mock_send.call_count == 1
            email = mock_send.call_args[0][0]
            assert email.recipients == ['nobody@example.org']
            assert email.subject == 'Codex test subject'
            assert email.body == 'test body'
