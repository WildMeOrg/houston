# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""
This file contains initialization data for development usage only.

You can execute this code via ``invoke app.db.init_development_data``
"""
from app.extensions import db, api

import uuid


DOCUMENTATION_CLIENT_GUID = uuid.UUID('d43216f8-7783-4c76-b9ce-944c96757822')
DOCUMENTATION_CLIENT_SECRET = (
    'v8cEpH899bfA8CglzMDTvsyyEzYJeYQgzsxFAIwEEjA0NbtGEvsCj4m1z25HoAUu'
)


def init_users():
    from app.modules.users.models import User

    with db.session.begin():
        root_user = User(
            email='root@localhost',
            password='q',
            is_active=True,
            is_admin=True,
        )
        db.session.add(root_user)

        docs_user = User(
            email='documentation@localhost',
            password='w',
            is_active=True,
        )
        db.session.add(docs_user)

        staff_member = User(
            email='staff@localhost',
            password='w',
            is_active=True,
            is_staff=True,
        )
        db.session.add(staff_member)

        regular_user = User(
            email='test@localhost',
            password='w',
            is_active=True,
        )
        db.session.add(regular_user)

        internal_user = User(
            email='internal@localhost',
            password='q',
            is_active=True,
            is_internal=True,
        )
        db.session.add(internal_user)

    return docs_user


def init_auth(docs_user):
    from app.modules.auth.models import OAuth2Client

    # TODO: OpenAPI documentation has to have OAuth2 Implicit Flow instead
    # of Resource Owner Password Credentials Flow
    with db.session.begin():
        oauth2_client = OAuth2Client(
            guid=DOCUMENTATION_CLIENT_GUID,
            secret=DOCUMENTATION_CLIENT_SECRET,
            user_guid=docs_user.guid,
            redirect_uris=[],
            default_scopes=api.api_v1.authorizations['oauth2_password']['scopes'],
        )
        db.session.add(oauth2_client)
    return oauth2_client


def init():
    from app.modules.users.models import User
    from app.modules.auth.models import OAuth2Client

    # Automatically update `default_scopes` for `documentation` OAuth2 Client,
    # as it is nice to have an ability to evaluate all available API calls.
    with db.session.begin():
        OAuth2Client.query.filter(OAuth2Client.guid == DOCUMENTATION_CLIENT_GUID).update(
            {
                OAuth2Client.default_scopes: api.api_v1.authorizations['oauth2_password'][
                    'scopes'
                ],
            }
        )

    assert (
        User.query.count() == 0
    ), 'Database is not empty. You should not re-apply fixtures! Aborted.'

    docs_user = init_users()  # pylint: disable=unused-variable
    init_auth(docs_user)
