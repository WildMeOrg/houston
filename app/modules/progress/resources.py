# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Progress resources
--------------------------
"""

import logging

from flask_restx._http import HTTPStatus

from app.extensions.api import Namespace
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from flask_restx_patched import Resource

from . import schemas
from .models import Progress

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('progress', description='Progress')  # pylint: disable=invalid-name


@api.route('/<uuid:progress_guid>')
@api.login_required(oauth_scopes=['progress:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Progress not found.',
)
@api.resolve_object_by_model(Progress, 'progress')
class ProgressByID(Resource):
    """
    Read-only external access for Progress trackers.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['progress'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedProgressSchema())
    def get(self, progress):
        """
        Get Progress details by ID.
        """
        return progress
