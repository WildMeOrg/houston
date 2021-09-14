# -*- coding: utf-8 -*-
from invoke import task


@task(default=True)
def shell(context):
    """Enter into IPython Shell with an initialized app"""
    import IPython
    from app import create_app

    app = create_app()
    del create_app

    with app.app_context():
        IPython.embed()
