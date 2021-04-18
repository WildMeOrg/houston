# -*- coding: utf-8 -*-
from ._utils import app_context_task


def bool_to_emoji(b):
    return '⭐' if b else '❌'


@app_context_task()
def check(context):
    """Check integration connectivity"""
    from flask import current_app as app

    max_service_len = 60
    header = f"{'Service': ^{max_service_len}} | Status"
    print(header)
    print('-' * len(header))

    service_checks = {
        'a': lambda a: True,
        'b': lambda a: False,
        'c': lambda a: True,
    }
    # Check connectivity to integration services
    for name, state_check in service_checks.items():
        status = bool_to_emoji(state_check(app))
        print(f'{name: <{max_service_len}} | {status}')
