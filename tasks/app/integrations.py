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


def check_edm(app):
    """Check for connectivity to EDM"""
    app.edm._ensure_initialized()
    return True


def check_gitlab(app):
    """Check the gitlab connection indirectly through the SubmissionManager"""
    app.sub.ensure_initialized()
    app.sub.gl.projects.list()
    return True


@app_context_task()
def check(context):
    """Check integration connectivity"""
    from flask import current_app as app

    service_checks = {
        f"db ({app.config['SQLALCHEMY_DATABASE_URI']})": check_db_connection,
        'gitlab': check_gitlab,
        'edm': check_edm,
        # ...
    }
    # Check connectivity to integration services
    for name, state_check in service_checks.items():
        status = bool_to_emoji(state_check(app))
        print(f'{status} {name}')
