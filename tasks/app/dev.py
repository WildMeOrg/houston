# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""
This file contains initialization data for development usage only.

You can execute this code via ``invoke app.dev``
"""
from app.extensions import db  # NOQA


from tasks.utils import app_context_task


@app_context_task
def embed(context):
    import utool as ut

    ut.embed()
