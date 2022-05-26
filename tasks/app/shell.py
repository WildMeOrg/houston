# -*- coding: utf-8 -*-
import logging

from invoke import task

log = logging.getLogger(__name__)


@task(default=True)
def shell(context):
    """Enter into IPython Shell with an initialized app"""
    import IPython

    from app import create_app

    app = create_app()
    del create_app

    log.info("The 'app' variable is the Flask app object")
    with app.app_context():
        IPython.embed()
