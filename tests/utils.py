# -*- coding: utf-8 -*-
"""
Testing utils
-------------
"""

from contextlib import contextmanager
from datetime import datetime, timedelta
import json

from flask import Response
from flask.testing import FlaskClient
from werkzeug.utils import cached_property
from app.extensions.auth import security
import config
import uuid
import shutil
import os


class AutoAuthFlaskClient(FlaskClient):
    """
    A helper FlaskClient class with a useful for testing ``login`` context
    manager.
    """

    def __init__(self, *args, **kwargs):
        super(AutoAuthFlaskClient, self).__init__(*args, **kwargs)
        self._user = None
        self._auth_scopes = None

    @contextmanager
    def login(self, user, auth_scopes=None):
        """
        Here is an example of how to use the login context

        with flask_app_client.login(user, auth_scopes=['users:read']):
            flask_app_client.get('/api/v1/users/')
        """
        self._user = user
        self._auth_scopes = auth_scopes or []
        yield self
        self._user = None
        self._auth_scopes = None

    def open(self, *args, **kwargs):
        if self._user is not None:
            from app.extensions import db
            from app.modules.auth.models import OAuth2Client, OAuth2Token

            oauth2_client = OAuth2Client(
                secret='SECRET',
                user=self._user,
                default_scopes=[],
            )

            oauth2_bearer_token = OAuth2Token(
                client=oauth2_client,
                user=self._user,
                token_type='Bearer',
                access_token='test_access_token',
                scopes=self._auth_scopes,
                expires=datetime.utcnow() + timedelta(days=1),
            )

            with db.session.begin():
                db.session.add(oauth2_bearer_token)

            extra_headers = (
                (
                    'Authorization',
                    '{token.token_type} {token.access_token}'.format(
                        token=oauth2_bearer_token
                    ),
                ),
            )
            if kwargs.get('headers'):
                kwargs['headers'] += extra_headers
            else:
                kwargs['headers'] = extra_headers

        response = super(AutoAuthFlaskClient, self).open(*args, **kwargs)

        if self._user is not None:
            with db.session.begin():
                db.session.delete(oauth2_bearer_token)
                db.session.delete(oauth2_bearer_token.client)

        return response


class JSONResponse(Response):
    # pylint: disable=too-many-ancestors
    """
    A Response class with extra useful helpers, i.e. ``.json`` property.
    """

    @cached_property
    def json(self):
        return json.loads(self.get_data(as_text=True))


# multiple tests clone a submission, do something with it and clean it up. Make sure this always happens using a
# class with a cleanup method to be called if any assertions fail
class CloneSubmission(object):
    def __init__(self, flask_app_client, user, submission_uuid, force_clone):
        from flask import current_app

        self.temp_submission = None
        submissions_database_path = config.TestingConfig.SUBMISSIONS_DATABASE_PATH
        self.submission_path = os.path.join(
            submissions_database_path, str(submission_uuid)
        )

        # Allow the option of forced cloning, this could raise an exception if the assertion fails
        # but this does not need to be in the try/except/finally construct as no resources are allocated yet
        if force_clone:
            if os.path.exists(self.submission_path):
                shutil.rmtree(self.submission_path)
            assert not os.path.exists(self.submission_path)

        # Use a backdoor way to clone this submission from EDM for testing
        self.temp_submission = current_app.sub.ensure_submission(submission_uuid, user)

    def remove_files(self):
        if os.path.exists(self.submission_path):
            shutil.rmtree(self.submission_path)

    def cleanup(self):
        # Restore original state
        if self.temp_submission is not None:
            self.temp_submission.delete()
            self.temp_submission = None
        self.remove_files()


# Clone the submission
# If later_usage is set, it's the callers responsibility to call the cleanup method.
def clone_submission(
    flask_app_client, user, submission_uuid, force_clone=False, later_usage=False
):
    clone = CloneSubmission(flask_app_client, user, submission_uuid, force_clone)
    if not later_usage:
        clone.cleanup()
    return clone


def generate_encounter_instance(user_email=None, user_password=None, user_full_name=None):
    """
    Returns:
        encounter_instance (Encounter) - a not committed to DB instance of a Encounter model.
    """
    user = generate_user_instance(
        email=user_email, password=user_password, full_name=user_full_name
    )
    from app.modules.encounters.models import Encounter

    return Encounter(owner=user)


def generate_user_instance(
    user_guid=None,
    email=None,
    password=None,
    full_name='First Middle Last',
    created=None,
    updated=None,
    is_active=True,
    is_staff=False,
    is_admin=False,
    is_internal=False,
    is_researcher=False,
    is_contributor=True,
    in_alpha=True,
):
    """
    Returns:
        user_instance (User) - an not committed to DB instance of a User model.
    """
    # pylint: disable=too-many-arguments
    from app.modules.users.models import User

    if user_guid is None:
        user_guid = uuid.uuid4()

    if email is None:
        email = '%s@localhost' % (email,)

    if password is None:
        password = security.generate_random(128)

    user_instance = User(
        guid=user_guid,
        full_name=full_name,
        password=password,
        email=email,
        created=created or datetime.now(),
        updated=updated or datetime.now(),
        is_active=is_active,
        is_staff=is_staff,
        is_admin=is_admin,
        is_internal=is_internal,
        is_researcher=is_researcher,
        is_contributor=is_contributor,
        in_alpha=in_alpha,
    )
    user_instance.password_secret = password
    return user_instance


def generate_submission_instance(owner):
    from app.modules.submissions.models import Submission

    submission_instance = Submission(guid=uuid.uuid4(), owner=owner)
    return submission_instance


def generate_asset_instance(submission_guid):
    from app.modules.assets.models import Asset

    asset_instance = Asset(
        guid=uuid.uuid4(),
        extension='None',
        path='FollowYourOwn',
        mime_type='Corporeal',
        magic_signature='42',
        filesystem_xxhash64='42',
        filesystem_guid=uuid.uuid4(),
        semantic_guid=uuid.uuid4(),
        submission_guid=submission_guid,
    )
    return asset_instance


def validate_dict_response(response, expected_code, expected_fields):
    assert response.status_code == expected_code
    # after some discussion, dropping the check of response.content_type
    # turns out response.json is very forgiving and tries to parse response.data
    # even when response.is_json == False ... so this allows for sloppy headers but valid json getting thru
    assert isinstance(response.json, dict)
    assert set(response.json.keys()) >= expected_fields


def validate_list_response(response, expected_code):
    assert response.status_code == expected_code
    assert response.content_type == 'application/json'
    assert isinstance(response.json, list)


def patch_test_op(value):
    return {
        'op': 'test',
        'path': '/current_password',
        'value': value,
    }


def patch_add_op(path, value):
    return {
        'op': 'add',
        'path': '/%s' % (path,),
        'value': value,
    }


def patch_remove_op(path, value=None):
    operation = {
        'op': 'remove',
        'path': '/%s' % (path,),
    }
    if value:
        operation['value'] = value

    return operation


def patch_replace_op(path, value):
    return {
        'op': 'replace',
        'path': '/%s' % (path,),
        'value': value,
    }
