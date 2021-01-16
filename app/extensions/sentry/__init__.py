# -*- coding: utf-8 -*-
"""
Logging adapter
---------------
"""
import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    Sentry extension initialization point.
    """
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    # if specified, setup sentry for exception reporting and runtime telemetry
    sentry_dsn = app.config.get('SENTRY_DSN', None)
    if sentry_dsn is not None:
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[FlaskIntegration()],
        )
