# -*- coding: utf-8 -*-
"""
Submission resources utils
-------------
"""
import json
import shutil
import os
import config
from tests import utils as test_utils

PATH = '/api/v1/submissions/'


def patch_submission(
    flask_app_client, submission_guid, user, data, expected_status_code=200
):
    with flask_app_client.login(user, auth_scopes=('submissions:write',)):
        response = flask_app_client.patch(
            '%s%s' % (PATH, submission_guid),
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(
            response, 200, {'guid', 'description', 'major_type'}
        )
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_submission(flask_app_client, user, submission_guid, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('submissions:read',)):
        response = flask_app_client.get('%s%s' % (PATH, submission_guid))

    if expected_status_code == 200:
        test_utils.validate_dict_response(
            response, 200, {'guid', 'description', 'major_type'}
        )
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_all_submissions(flask_app_client, user, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('submissions:read',)):
        response = flask_app_client.get(PATH)

    if expected_status_code == 200:
        test_utils.validate_list_response(response, 200)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def delete_submission(flask_app_client, user, submission_guid, expected_status_code=204):
    with flask_app_client.login(user, auth_scopes=('submissions:write',)):
        response = flask_app_client.delete('%s%s' % (PATH, submission_guid))

    if expected_status_code == 204:
        assert response.status_code == 204
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )


# multiple tests clone a submission, do something with it and clean it up. Make sure this always happens using a
# class with a cleanup method to be called if any assertions fail
class CloneSubmission(object):
    def __init__(self, flask_app_client, admin_user, user, submission_guid, force_clone):
        from app.modules.submissions.models import Submission

        self.submission = None
        self.guid = submission_guid

        # Allow the option of forced cloning, this could raise an exception if the assertion fails
        # but this does not need to be in any try/except/finally construct as no resources are allocated yet
        if force_clone:
            database_path = config.TestingConfig.SUBMISSIONS_DATABASE_PATH
            submission_path = os.path.join(database_path, str(submission_guid))

            if os.path.exists(submission_path):
                shutil.rmtree(submission_path)
            assert not os.path.exists(submission_path)

        with flask_app_client.login(user, auth_scopes=('submissions:read',)):
            self.response = flask_app_client.get('%s%s' % (PATH, submission_guid))

        if self.response.status_code == 428:

            with flask_app_client.login(admin_user, auth_scopes=('submissions:write',)):
                self.response = flask_app_client.post('%s%s' % (PATH, submission_guid))

            # only store the transient submission for cleanup if the clone worked
            if self.response.status_code == 200:
                self.submission = Submission.query.get(self.response.json['guid'])

            # reassign ownership
            data = [
                test_utils.patch_add_op('owner', '%s' % user.guid),
            ]
            patch_submission(flask_app_client, submission_guid, admin_user, data)

            # and read it back as the real user
            with flask_app_client.login(user, auth_scopes=('submissions:read',)):
                self.response = flask_app_client.get('%s%s' % (PATH, submission_guid))

    def remove_files(self):
        database_path = config.TestingConfig.SUBMISSIONS_DATABASE_PATH
        submission_path = os.path.join(database_path, str(self.guid))
        if os.path.exists(submission_path):
            shutil.rmtree(submission_path)

    def cleanup(self):
        # Restore original state
        if self.submission is not None:
            self.submission.delete()
            self.submission = None
        self.remove_files()


# Clone the submission
# If later_usage is set, it's the callers responsibility to call the cleanup method.
def clone_submission(
    flask_app_client,
    admin_user,
    user,
    submission_uuid,
    force_clone=False,
    later_usage=False,
):
    clone = CloneSubmission(
        flask_app_client, admin_user, user, submission_uuid, force_clone
    )
    if not later_usage:
        clone.cleanup()
    return clone
