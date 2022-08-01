# -*- coding: utf-8 -*-
"""
Application Users management related tasks for Invoke.
"""

from tasks.utils import app_context_task


@app_context_task(help={'email': 'temp@localhost'})
def create_user(
    context,
    email,
):
    from app.modules.users.models import User

    """
    Create a new user.
    """

    password = input('Enter password: ')

    new_user = User(password=password, email=email, is_active=True, is_contributor=True)

    from app.extensions import db

    with db.session.begin():
        db.session.add(new_user)


@app_context_task(
    help={
        'email': 'temp@localhost',
        'role': 'role name, Admin, Staff, Internal, Researcher, Contributor, Exporter',
    }
)
def add_role(context, email, role):
    """
    Update a given user (email) to have a role (Admin, Staff, Internal, Researcher, Contributor, Exporter)
    """
    from app.extensions import db
    from app.modules.users.models import User

    user = User.find(email=email)

    if user is None:
        print("User with email '%s' does not exist." % email)
        print('\nNo updates applied.')
        return

    role = role.lower()

    if role in ['admin', 'administrator']:
        print('Found user:\n\t{!r}'.format(user))
        answer = input(
            'Are you sure you want to promote the above found user to a site administrator? [Y / N]: '
        )
        answer = answer.strip().lower()

        user.is_admin = True
    elif role in ['staff', 'developer']:
        user.is_staff = True
    elif role in ['internal']:
        user.is_internal = True
    elif role in ['researcher']:
        user.is_researcher = True
    elif role in ['contributor']:
        user.is_contributor = True
    elif role in ['exporter']:
        user.is_exporter = True
    else:
        print('Role {} not supported' % role)
        return

    # User role changed, update DB
    with db.session.begin():
        db.session.merge(user)
    db.session.refresh(user)


@app_context_task(
    help={
        'email': 'temp@localhost',
        'role': 'role name, Admin, Staff, Internal, Researcher, Contributor, Exporter',
    }
)
def remove_role(context, email, role):
    """
    Update a given user (email) to not have a role (Admin, Staff, Internal, Researcher, Contributor, Exporter)
    """
    from app.extensions import db
    from app.modules.users.models import User

    user = User.find(email=email)

    if user is None:
        print("User with email '%s' does not exist." % email)
        print('\nNo updates applied.')
        return

    role = role.lower()

    if role in ['admin', 'administrator']:
        user.is_admin = False
    elif role in ['staff', 'developer']:
        user.is_staff = False
    elif role in ['internal']:
        user.is_internal = False
    elif role in ['researcher']:
        user.is_researcher = False
    elif role in ['contributor']:
        user.is_contributor = False
    elif role in ['exporter']:
        user.is_exporter = False
    else:
        print('Role {} not supported' % role)
        return

    # User role changed, update DB
    with db.session.begin():
        db.session.merge(user)
    db.session.refresh(user)


@app_context_task
def create_oauth2_client(context, email, guid, secret, default_scopes=None):
    """
    Create a new OAuth2 Client associated with a given user (email).
    """
    from app.modules.auth.models import OAuth2Client
    from app.modules.users.models import User

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
    from app.modules.users.models import User

    users = User.query.all()
    for user in users:
        print('User : {} '.format(user))
