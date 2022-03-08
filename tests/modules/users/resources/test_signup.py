# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from unittest import mock
import uuid
import tests.modules.users.resources.utils as user_utils
from app.modules import is_module_enabled


# from config import get_preliminary_config


# def test_recaptcha(flask_app_client):
#     response = flask_app_client.get('/api/v1/auth/recaptcha')
#     assert response.status_code == 200
#     assert response.content_type == 'application/json'
#     assert set(response.json.keys()) == {'recaptcha_public_key'}
#     assert (
#         response.json['recaptcha_public_key'] == get_preliminary_config().RECAPTCHA_PUBLIC_KEY
#     )


def create_new_user(flask_app_client, data, must_succeed=True):
    """
    Helper function for valid new user creation.
    """
    # _data = {
    #     'recaptcha_key': get_preliminary_config().RECAPTCHA_BYPASS,
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
    with mock.patch('app.extensions.email.mail.send') as send:
        user_guid = create_new_user(
            flask_app_client,
            data={'email': 'user1@localhost', 'password': 'user1_password'},
        )
    assert isinstance(user_guid, uuid.UUID)
    assert send.called
    email = send.call_args[0][0]
    assert email.recipients == ['user1@localhost']
    assert 'verify' in email.html.lower()

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
        'message': 'You must be an admin, user manager or privileged to set roles for a new user',
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
        'message': 'You must be an admin, user manager or privileged to set roles for a new user',
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
        'message': 'You must be an admin, user manager or privileged to set roles for a new user',
    }


def test_new_user_creation_roles_user_manager(flask_app_client, user_manager_user):
    with flask_app_client.login(user_manager_user):
        create_new_user(
            flask_app_client,
            data={
                'email': 'user42@localhost',
                'password': 'password',
                'roles': ['in_alpha'],
            },
        )


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

    valid_roles = (
        'is_interpreter, is_data_manager, is_user_manager, '
        'is_contributor, is_researcher, is_exporter, is_admin, is_active, in_alpha, in_beta'
    )
    assert response.status_code == 422
    assert response.content_type == 'application/json'
    assert response.json == {
        'status': 422,
        'message': f'invalid roles: is_researcher2.  Valid roles are {valid_roles}',
    }

    data = {
        'email': 'user1@localhost',
        'password': 'password',
        'roles': ['in_alpha', 'is_admin', 'is_researcher', 'is_staff'],
    }
    error = f'invalid roles: is_staff.  Valid roles are {valid_roles}'
    user_utils.create_user(flask_app_client, admin_user, data, 422, error)

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
    from app.modules.notifications.models import NOTIFICATION_DEFAULTS

    desired_schema = {
        'affiliation': '',
        'created': response.json['created'],
        'email': 'user1@localhost',
        'forum_id': '',
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
        'is_email_confirmed': False,
        'location': '',
        'profile_fileupload': None,
        'updated': response.json['updated'],
        'viewed': response.json['viewed'],
        'website': None,
        'collaborations': [],
        'individual_merge_requests': [],
        'notification_preferences': NOTIFICATION_DEFAULTS,
    }

    if is_module_enabled('missions'):
        desired_schema['owned_missions'] = []
        desired_schema['owned_mission_tasks'] = []

    assert response.json == desired_schema

    # Cleanup
    from app.modules.users.models import User

    user1_instance = User.query.get(user_guid)
    with db.session.begin():
        db.session.delete(user1_instance)


def test_user_creation_deactivation_reactivation_user_manager(
    flask_app_client, user_manager_user, request, db
):
    data = {
        'email': 'user1@localhost',
        'password': 'user1_password',
        'full_name': 'My name',
    }
    create_resp = user_utils.create_user(flask_app_client, None, data)

    from app.modules.users.models import User

    user_instance = User.query.get(create_resp.json['guid'])
    request.addfinalizer(lambda: db.session.delete(user_instance))

    # Delete (deactivate) user
    user_utils.delete_user(flask_app_client, user_instance)

    assert '@deactivated' in user_instance.email
    assert user_instance.full_name == 'Inactivated User'

    user_utils.create_user(
        flask_app_client,
        None,
        data,
        409,
        'The email address is already in use in an inactivated user.',
    )

    recreate_resp = user_utils.create_user(flask_app_client, user_manager_user, data)

    assert create_resp.json['guid'] == recreate_resp.json['guid']
