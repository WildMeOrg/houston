# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Submissions resources
--------------------------
"""

import logging
import werkzeug

from flask import request
from flask_login import current_user
from flask_restplus_patched import Resource
from flask_restplus._http import HTTPStatus

from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.extensions.tus import tus_upload_dir
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation

from . import parameters, schemas
from .models import Submission
import os


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
        repo, project = submission.ensure_repository()
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

        repo, project = submission.ensure_repository()

        for upload_file in request.files.getlist('files'):
            submission.git_write_upload_file(upload_file)

        submission.git_commit('Initial commit via %s' % (request.url_rule,))

        submission.git_push()

        return submission


@api.route('/<uuid:submission_guid>')
@api.login_required(oauth_scopes=['submissions:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Submission not found.',
)
@api.resolve_object_by_model(Submission, 'submission', return_not_found=True)
class SubmissionByID(Resource):
    """
    Manipulations with a specific Submission.
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
        """
        Get Submission details by ID.

        If submission is not found locally in database, a None submission
        will be returned.

        In this event, check SubmissionManager for remote Submission
        by UUID, if not found, throw 404 as intended
        """
        submission, submission_guids = submission

        if submission is None:
            # We have checked the submission manager and cannot find this submission, raise 404 manually
            raise werkzeug.exceptions.NotFound

        return submission

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['submission'],
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
        """
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
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['submission'],
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

        repo, project = submission.ensure_repository()
        updir = tus_upload_dir(submission.guid)
        submission_abspath = submission.get_absolute_path()
        submission_path = os.path.join(submission_abspath, '_submission')
        ct = 0
        for root, dirs, files in os.walk(updir):
            ct = len(files)
            for name in files:
                log.debug(
                    'moving upload %r to sub dir %r'
                    % (
                        name,
                        submission_path,
                    )
                )
                os.rename(os.path.join(root, name), os.path.join(submission_path, name))

        if ct > 0:
            log.info('Tus collect for %d files moved' % (ct))
            submission.git_commit('Tus collect commit for %d files.' % (ct,))
            submission.git_push()

        return submission
