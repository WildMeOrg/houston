# -*- coding: utf-8 -*-
"""
Logging adapter
---------------
"""
import logging

from flask_restx_patched import is_extension_enabled

if not is_extension_enabled('stripe'):
    raise RuntimeError('Stripe is not enabled')


log = logging.getLogger(__name__)  # pylint: disable=invalid-name


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    Stripe extension initialization point.
    """
    import stripe  # NOQA

    # Initialize Stripe payment
    stripe.api_key = app.config.get('STRIPE_SECRET_KEY')
