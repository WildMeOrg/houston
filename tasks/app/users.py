# -*- coding: utf-8 -*-
"""
Application Users management related tasks for Invoke.
"""

from ._utils import app_context_task
from app.modules.users.models import User

@app_context_task(help={'email': 'temp@localhost'})
def create_user(
    context,
    email,
    is_internal=False,
    is_admin=False,
    is_staff=False,
    is_active=True,
):
    """
    Create a new user.
    """

    password = input('Enter password: ')

    new_user = User(
        password=password,
        email=email,
        is_internal=is_internal,
        is_admin=is_admin,
        is_staff=is_staff,
        is_active=is_active,
    )

    from app.extensions import db

    with db.session.begin():
        db.session.add(new_user)


@app_context_task(help={'email': 'temp@localhost'})
def promote_to_admin(
    context,
    email,
):
    """
    Promote a given user (email) to administrator permissions
    """
    from app.modules.users.models import User

    user = User.find(email=email)

    if user is None:
        print("User with email '%s' does not exist." % email)
        print('\nNo updates applied.')
        return

    if user.is_admin:
        print('The given user is already an administrator:\n\t%r' % (user,))
        print('\nNo updates applied.')
        return

    user.is_admin = True

    print('Found user:\n\t%r' % (user,))
    answer = input(
        'Are you sure you want to promote the above found user to a site administrator? [Y / N]: '
    )
    answer = answer.strip().lower()

    if answer not in ['y', 'yes']:
        print('Confirmation failed.')
        print('\nNo updates applied.')

    from app.extensions import db

    with db.session.begin():
        db.session.merge(user)
    db.session.refresh(user)

    assert user.is_admin
    print('\nThe user was successfully promoted to an administrator.')


@app_context_task
def create_oauth2_client(context, email, guid, secret, default_scopes=None):
    """
    Create a new OAuth2 Client associated with a given user (email).
    """
    from app.modules.auth.models import OAuth2Client

    user = User.find(email=email)

    if user is None:
        raise Exception("User with email '%s' does not exist." % email)

    if default_scopes is None:
        from app.extensions.api import api_v1

        default_scopes = list(api_v1.authorizations['oauth2_password']['scopes'].keys())

    oauth2_client = OAuth2Client(
        guid=guid,
        secret=secret,
        user=user,
        default_scopes=default_scopes,
    )

    from app.extensions import db

    with db.session.begin():
        db.session.add(oauth2_client)


@app_context_task
def list_all(context):
    """
    Show existing users.
    """

    users = User.query.all()
    for user in users:
        print("User : {} ".format(user))

@app_context_task
def sync_edm(context, refresh = False):
    """
    Sync the users from the EDM onto the local Hudson
    """
    User.edm_sync_all(refresh=refresh)


