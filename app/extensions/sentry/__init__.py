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
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
    except ImportError:
        pass
    else:
        try:
            sentry_dsn = app.config.get('SENTRY_DSN', None)
            if (
                sentry_dsn is not None
                and isinstance(sentry_dsn, str)
                and len(sentry_dsn) > 0
            ):
                sentry_sdk.init(
                    sentry_dsn,
                    integrations=[FlaskIntegration()],
                    traces_sample_rate=1.0,
                )
        except Exception:
            pass
