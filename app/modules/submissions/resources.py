# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Submissions resources
--------------------------
"""

import logging
import werkzeug
import uuid

from flask import request, current_app
from flask_login import current_user
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus

from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation

from . import parameters, schemas
from .models import Submission


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('submissions', description='Submissions')  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['submissions:read'])
class Submissions(Resource):
    """
    Manipulations with Submissions.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Submission,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseSubmissionSchema(many=True))
    def get(self, args):
        """
        List of Submission.

        Returns a list of Submission starting from ``offset`` limited by ``limit``
        parameter.
        """
        return Submission.query.offset(args['offset']).limit(args['limit'])

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Submission,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['submissions:write'])
    @api.parameters(parameters.CreateSubmissionParameters())
    @api.response(schemas.DetailedSubmissionSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        r"""
        Create a new instance of Submission.

        CommandLine:
            EMAIL='test@localhost'
            PASSWORD='test'
            TIMESTAMP=$(date '+%Y%m%d-%H%M%S%Z')
            curl \
                -X POST \
                -c cookie.jar \
                -F email=${EMAIL} \
                -F password=${PASSWORD} \
                https://houston.dyn.wildme.io/api/v1/auth/sessions | jq
            curl \
                -X GET \
                -b cookie.jar \
                https://houston.dyn.wildme.io/api/v1/users/me | jq
            curl \
                -X POST \
                -b cookie.jar \
                -F description="This is a test submission (via CURL), please ignore" \
                https://houston.dyn.wildme.io/api/v1/submissions/ | jq
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Submission'
        )
        with context:
            args['owner_guid'] = current_user.guid
            submission = Submission(**args)
            db.session.add(submission)

        # Get the repo to make sure it's configured
        current_app.agm.get_repository(submission)
        return submission


@api.route('/streamlined')
@api.login_required(oauth_scopes=['submissions:write'])
class SubmissionsStreamlined(Resource):
    """
    Manipulations with Submissions + File add/commit.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Submission,
            'action': AccessOperation.WRITE,
        },
    )
    @api.parameters(parameters.CreateSubmissionParameters())
    @api.response(schemas.DetailedSubmissionSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        r"""
        Create a new instance of Submission.

        CommandLine:
            EMAIL='test@localhost'
            PASSWORD='test'
            TIMESTAMP=$(date '+%Y%m%d-%H%M%S%Z')
            curl \
                -X POST \
                -c cookie.jar \
                -F email=${EMAIL} \
                -F password=${PASSWORD} \
                https://houston.dyn.wildme.io/api/v1/auth/sessions | jq
            curl \
                -X GET \
                -b cookie.jar \
                https://houston.dyn.wildme.io/api/v1/users/me | jq
            curl \
                -X POST \
                -b cookie.jar \
                -F description="This is a test submission (via CURL), please ignore" \
                -F files="@tests/submissions/test-000/zebra.jpg" \
                -F files="@tests/submissions/test-000/fluke.jpg" \
                https://houston.dyn.wildme.io/api/v1/submissions/streamlined | jq
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Submission'
        )
        with context:
            args['owner_guid'] = current_user.guid
            submission = Submission(**args)
            db.session.add(submission)

        # Get the repo to make sure it's configured
        current_app.agm.get_repository(submission)

        for upload_file in request.files.getlist('files'):
            submission.git_write_upload_file(upload_file)

        submission.git_commit('Initial commit via %s' % (request.url_rule,))

        submission.git_push()

        return submission


@api.login_required(oauth_scopes=['submissions:read'])
@api.route('/<uuid:submission_guid>')
@api.resolve_object_by_model(Submission, 'submission', return_not_found=True)
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Submission not found.',
)
@api.response(
    code=HTTPStatus.PRECONDITION_REQUIRED,
    description='Submission not local, need to post',
)
class SubmissionByID(Resource):
    """
    Manipulations with a specific Submission.
    """

    # the resolve_object_by_model returns a tuple if the return_not_found is set as it is here
    # a common helper to get the submission object or raise 428 if remote only
    def _get_submission_with_428(self, submission):
        submission, submission_guids = submission
        if submission is not None:
            return submission

        # We did not find the submission by its UUID in the Houston database
        # We now need to check the SubmissionManager for the existence of that repo
        submission_guid = submission_guids[0]
        assert isinstance(submission_guid, uuid.UUID)

        if current_app.agm.is_asset_group_on_remote(submission_guid):
            # Submission is not local but is on remote
            log.info(f'Submission {submission_guid} on remote but not local')
            raise werkzeug.exceptions.PreconditionRequired
        else:
            # Submission neither local nor remote
            return None

    @api.permission_required(
        permissions.ModuleOrObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Submission,
            'obj': kwargs['submission'][0],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedSubmissionSchema())
    def get(self, submission):
        """
        Get Submission details by ID.

        If submission is not found locally in database, but is on the remote Github,
        a 428 PRECONDITION_REQUIRED will be returned.

        If submission is not local and not on remote github, 404 will be returned.

        Otherwise the submission will be returned
        """
        submission = self._get_submission_with_428(submission)
        if submission is None:
            raise werkzeug.exceptions.NotFound

        return submission

    @api.login_required(oauth_scopes=['submissions:write'])
    @api.permission_required(
        permissions.ModuleOrObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Submission,
            'obj': kwargs['submission'][0],
            'action': AccessOperation.WRITE,
        },
    )
    @api.response(schemas.DetailedSubmissionSchema())
    def post(self, submission):
        """
        Post Submission details by ID. (Actually a get with clone)

        If submission is not found locally in database, but is on the remote Github,
        it will be cloned from the remote github

        If submission is not local and not on remote github, 404 will be returned.

        Otherwise the submission will be returned
        """
        submission, submission_guids = submission
        if submission is not None:
            log.info(f'Submission {submission.guid} found locally on post')
            return submission

        # We did not find the submission by its UUID in the Houston database
        # We now need to check the SubmissionManager for the existence of that repo
        submission_guid = submission_guids[0]
        assert isinstance(submission_guid, uuid.UUID)

        # Clone if present on gitlab
        submission = Submission.ensure_asset_group(submission_guid)
        if submission is None:
            # We have checked the submission manager and cannot find this submission, raise 404 manually
            raise werkzeug.exceptions.NotFound

        return submission

    @api.permission_required(
        permissions.ModuleOrObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Submission,
            'obj': kwargs['submission'][0],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['submissions:write'])
    @api.parameters(parameters.PatchSubmissionDetailsParameters())
    @api.response(schemas.DetailedSubmissionSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, submission):
        """
        Patch Submission details by ID.

        If submission is not found locally in database, but is on the remote Github,
        a 428 PRECONDITION_REQUIRED will be returned.

        If submission is not local and not on remote github, 404 will be returned.

        Otherwise the submission will be patched
        """
        submission = self._get_submission_with_428(submission)
        if submission is None:
            raise werkzeug.exceptions.NotFound

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Submission details.'
        )
        with context:
            parameters.PatchSubmissionDetailsParameters.perform_patch(
                args, obj=submission
            )
            db.session.merge(submission)
        return submission

    @api.permission_required(
        permissions.ModuleOrObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Submission,
            'obj': kwargs['submission'][0],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['submissions:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, submission):
        """
        Delete a Submission by ID.
        """
        submission = self._get_submission_with_428(submission)

        if submission is not None:
            context = api.commit_or_abort(
                db.session, default_error_message='Failed to delete the Submission.'
            )
            with context:
                db.session.delete(submission)
        return None


@api.route('/tus/collect/<uuid:submission_guid>')
@api.login_required(oauth_scopes=['submissions:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Submission not found.',
)
@api.resolve_object_by_model(Submission, 'submission', return_not_found=True)
class SubmissionTusCollect(Resource):
    """
    Collect files uploaded by Tus endpoint for this Submission
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['submission'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedSubmissionSchema())
    def get(self, submission):
        submission, submission_guids = submission

        if submission is None:
            # We have checked the submission manager and cannot find this submission, raise 404 manually
            raise werkzeug.exceptions.NotFound

        submission.import_tus_files()

        return submission
