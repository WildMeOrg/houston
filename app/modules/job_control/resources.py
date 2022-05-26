# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API JobControl resources
--------------------------
"""

import logging

from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from flask_restx_patched import Resource

from .models import JobControl

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('job-control', description='Job Control')  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['jobs:read'])
class Jobs(Resource):
    """
    Manipulations with Jobs.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': JobControl,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    def get(self, args):
        """
        List of Jobs, just guid time and status.

        Returns a list of Jobs starting from ``offset`` limited by ``limit``
        parameter.
        """

        # TODO do we want to sort these in reverse date order so you get the last 'limit' jobs
        offset = args['offset']
        limit = args['limit']
        jobs = JobControl.get_jobs(verbose=False)[offset : offset + limit]
        returned_jobs = []
        for job in jobs:
            returned_jobs.append(
                {
                    'object_guid': job['object_guid'],
                    'job_id': job['job_id'],
                    'type': job['type'],
                    'start': job['start'],
                    'active': job['active'],
                }
            )

        return returned_jobs


@api.route('/debug')
@api.login_required(oauth_scopes=['jobs:read'])
class JobsDebug(Resource):
    """
    Manipulations with Jobs.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': JobControl,
            'action': AccessOperation.READ_DEBUG,
        },
    )
    @api.parameters(PaginationParameters())
    def get(self, args):
        """
        List of Jobs, full contents

        Returns a list of Jobs starting from ``offset`` limited by ``limit``
        parameter.
        """

        # TODO do we want to sort these in reverse date order so you get the last 'limit' jobs
        return JobControl.get_jobs(verbose=True)
