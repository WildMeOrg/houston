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

    def __init__(self, flask_app_client, regular_user, submission_uuid, force_clone):
        from app.modules.submissions.models import Submission

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

        with flask_app_client.login(regular_user, auth_scopes=('submissions:read',)):
            self.response = flask_app_client.get(
                '/api/v1/submissions/%s' % submission_uuid
            )

        self.temp_submission = Submission.query.get(self.response.json['guid'])

    def remove_files(self):
        if os.path.exists(self.submission_path):
            shutil.rmtree(self.submission_path)

    def cleanup(self):
        # Restore original state
        if self.temp_submission is not None:
            self.temp_submission.delete()
            self.temp_submission = None
        self.remove_files()


# Clone the submission within a try/except/finally structure to ensure that cleanup is called to clean up
# the files etc.
# If later_usage is set, it's the callers responsibility to call the cleanup method.
def clone_submission(flask_app_client, regular_user, submission_uuid, force_clone = False, later_usage = False):
    clone = CloneSubmission(flask_app_client, regular_user, submission_uuid, force_clone)
    try:
        assert clone.response.status_code == 200
        assert clone.response.content_type == 'application/json'
        assert isinstance(clone.response.json, dict)
        assert set(clone.response.json.keys()) >= {'guid', 'owner_guid', 'major_type', 'commit'}
        assert clone.response.json.get('guid') == str(submission_uuid)

    except Exception as ex:
        clone.cleanup()
        raise ex
    finally:
        if not later_usage:
            clone.cleanup()
    return clone

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
    )
    user_instance.password_secret = password
    return user_instance
