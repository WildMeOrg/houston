# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

# import config


# def test_recaptcha(flask_app_client):
#     response = flask_app_client.get('/api/v1/auth/recaptcha')
#     assert response.status_code == 200
#     assert response.content_type == 'application/json'
#     assert set(response.json.keys()) == {'recaptcha_public_key'}
#     assert (
#         response.json['recaptcha_public_key'] == config.TestingConfig.RECAPTCHA_PUBLIC_KEY
#     )


def create_new_user(flask_app_client, data, must_succeed=True):
    """
    Helper function for valid new user creation.
    """
    # _data = {
    #     'recaptcha_key': config.TestingConfig.RECAPTCHA_BYPASS,
    # }
    # _data.update(data)
    # response = flask_app_client.post('/api/v1/users/', data=_data)
    response = flask_app_client.post('/api/v1/users/', data=data)

    if must_succeed:
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert set(response.json.keys()) >= {'guid', 'email'}
        return uuid.UUID(response.json['guid'])
    return response


def test_new_user_creation(patch_User_password_scheme, flask_app_client, db):
    # pylint: disable=invalid-name,unused-argument
    user_guid = create_new_user(
        flask_app_client,
        data={'email': 'user1@localhost', 'password': 'user1_password'},
    )
    assert isinstance(user_guid, uuid.UUID)

    # Cleanup
    from app.modules.users.models import User

    user1_instance = User.query.get(user_guid)
    assert user1_instance.email == 'user1@localhost'
    assert user1_instance.password == 'user1_password'

    with db.session.begin():
        db.session.delete(user1_instance)


# def test_new_user_creation_without_captcha_must_fail(flask_app_client):
#     # pylint: disable=invalid-name
#     response = create_new_user(
#         flask_app_client,
#         data={
#             'recaptcha_key': None,
#             'email': 'user1@localhost',
#             'password': 'user1_password',
#         },
#         must_succeed=False,
#     )
#     assert response.status_code == 403
#     assert response.content_type == 'application/json'
#     assert set(response.json.keys()) >= {'status', 'message'}

# def test_new_user_creation_with_incorrect_captcha_must_fail(flask_app_client):
#     # pylint: disable=invalid-name
#     response = create_new_user(
#         flask_app_client,
#         data={
#             'recaptcha_key': 'invalid_captcha_key',
#             'email': 'user1@localhost',
#             'password': 'user1_password',
#         },
#         must_succeed=False,
#     )
#     assert response.status_code == 403
#     assert response.content_type == 'application/json'
#     assert set(response.json.keys()) >= {'status', 'message'}

# def test_new_user_creation_without_captcha_but_admin_user(
#     patch_User_password_scheme, flask_app_client, admin_user, db
# ):
#     # pylint: disable=invalid-name,unused-argument
#     with flask_app_client.login(admin_user):
#         user_guid = create_new_user(
#             flask_app_client,
#             data={
#                 'recaptcha_key': None,
#                 'email': 'user1@localhost',
#                 'password': 'user1_password',
#             },
#         )
#     assert isinstance(user_guid, uuid.UUID)

#     # Cleanup
#     from app.modules.users.models import User

#     user1_instance = User.query.get(user_guid)
#     assert user1_instance.email == 'user1@localhost'
#     assert user1_instance.password == 'user1_password'

#     with db.session.begin():
#         db.session.delete(user1_instance)


def test_new_user_creation_duplicate_must_fail(flask_app_client, db):
    # pylint: disable=invalid-name
    user_guid = create_new_user(
        flask_app_client,
        data={'email': 'user1@localhost', 'password': 'user1_password'},
    )
    response = create_new_user(
        flask_app_client,
        data={'email': 'user1@localhost', 'password': 'user1_password'},
        must_succeed=False,
    )
    assert response.status_code == 409
    assert response.content_type == 'application/json'
    assert set(response.json.keys()) >= {'status', 'message'}

    # Cleanup
    from app.modules.users.models import User

    user1_instance = User.query.get(user_guid)
    with db.session.begin():
        db.session.delete(user1_instance)


def test_new_user_creation_no_password_must_fail(flask_app_client):
    # pylint: disable=invalid-name
    response = create_new_user(
        flask_app_client,
        data={'email': 'user1@localhost'},
        must_succeed=False,
    )

    assert response.status_code == 422
    assert response.content_type == 'application/json'
    assert set(response.json.keys()) >= {'status', 'message'}


def test_new_user_creation_roles_anonymous(flask_app_client):
    response = create_new_user(
        flask_app_client,
        data={
            'email': 'user1@localhost',
            'password': 'password',
            'roles': ['in_alpha'],
        },
        must_succeed=False,
    )

    assert response.status_code == 403
    assert response.content_type == 'application/json'
    assert response.json == {
        'status': 403,
        'message': 'You must be an admin or privileged to set roles for a new user',
    }


def test_new_user_creation_roles_unprivileged(flask_app_client, regular_user):
    response = create_new_user(
        flask_app_client,
        data={
            'email': 'user1@localhost',
            'password': 'password',
            'roles': ['in_alpha'],
        },
        must_succeed=False,
    )

    assert response.status_code == 403
    assert response.content_type == 'application/json'
    assert response.json == {
        'status': 403,
        'message': 'You must be an admin or privileged to set roles for a new user',
    }

    with flask_app_client.login(regular_user):
        response = create_new_user(
            flask_app_client,
            data={
                'email': 'user1@localhost',
                'password': 'password',
                'roles': ['in_alpha'],
            },
            must_succeed=False,
        )

    assert response.status_code == 403
    assert response.content_type == 'application/json'
    assert response.json == {
        'status': 403,
        'message': 'You must be an admin or privileged to set roles for a new user',
    }


def test_new_user_creation_roles_admin(flask_app_client, admin_user, db):
    with flask_app_client.login(admin_user):
        response = create_new_user(
            flask_app_client,
            data={
                'email': 'user1@localhost',
                'password': 'password',
                'roles': ['in_alpha', 'is_admin', 'is_researcher2'],
            },
            must_succeed=False,
        )

    assert response.status_code == 422
    assert response.content_type == 'application/json'
    assert response.json == {
        'status': 422,
        'message': 'invalid roles: is_researcher2.  Valid roles are is_user_manager, is_contributor, is_researcher, is_exporter, is_internal, is_admin, is_staff, is_active, in_alpha, in_beta',
    }

    with flask_app_client.login(admin_user):
        response = create_new_user(
            flask_app_client,
            data={
                'email': 'user1@localhost',
                'password': 'password',
                'roles': ['in_alpha', 'is_admin', 'is_researcher'],
            },
            must_succeed=False,
        )

    assert response.status_code == 200
    assert response.content_type == 'application/json'
    user_guid = response.json['guid']
    assert response.json == {
        'affiliation': None,
        'created': response.json['created'],
        'email': 'user1@localhost',
        'forum_id': None,
        'full_name': '',
        'guid': user_guid,
        'in_alpha': True,
        'in_beta': False,
        'is_active': True,
        'is_admin': True,
        'is_contributor': False,
        'is_exporter': False,
        'is_internal': False,
        'is_researcher': True,
        'is_staff': False,
        'is_user_manager': False,
        'location': None,
        'profile_fileupload': None,
        'updated': response.json['updated'],
        'viewed': response.json['viewed'],
        'website': None,
    }

    # Cleanup
    from app.modules.users.models import User

    user1_instance = User.query.get(user_guid)
    with db.session.begin():
        db.session.delete(user1_instance)
