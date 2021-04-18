# -*- coding: utf-8 -*-
from ._utils import app_context_task


def bool_to_emoji(b):
    return '⭐' if b else '❌'


def check_db_connection(_app):
    """Check the database connection"""
    from app.extensions import db

    with db.engine.connect() as conn:
        results = conn.execute('select 1;')
        return list(results) == [(1,)]


@app_context_task()
def check(context):
    """Check integration connectivity"""
    from flask import current_app as app

    max_service_len = 60
    header = f"{'Service': ^{max_service_len}} | Status"
    print(header)
    print('-' * len(header))

    service_checks = {
        f"db ({app.config['SQLALCHEMY_DATABASE_URI']})": check_db_connection,
        # ...
    }
    # Check connectivity to integration services
    for name, state_check in service_checks.items():
        status = bool_to_emoji(state_check(app))
        print(f'{name: <{max_service_len}} | {status}')
