# -*- coding: utf-8 -*-
"""
Application config management related tasks for Invoke.
"""

from tasks.utils import app_context_task


@app_context_task
def show(context):
    """
    Show application configuration data
    """
    from functools import reduce

    from flask import current_app

    config = current_app.config
    max_key_len = reduce(
        lambda x, y: max(isinstance(x, str) and len(x) or x, len(y)), config.keys()
    )

    print(f"{'Config Key': ^{max_key_len}} | Value")
    print('-' * 78)
    for key, value in config.items():
        print(f'{key: <{max_key_len}} | {value}')
