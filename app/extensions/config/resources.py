# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods
"""
RESTful API Config resources
--------------------------
"""

import logging

from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus

from app.extensions.api import Namespace

from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation

from app.modules.ia_config_reader import IaConfig

from . import parameters
from .models import HoustonConfig

log = logging.getLogger(__name__)
api = Namespace('config/houston', description='HoustonConfig')


@api.route('/houston')
@api.login_required(oauth_scopes=['config.houston:read'])
class HoustonConfigs(Resource):
    """
    Manipulations with configs.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': HoustonConfig,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['config.houston:write'])
    @api.parameters(parameters.PatchHoustonConfigParameters())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args):
        """
        Patch config details by ID.
        """
        response = parameters.PatchHoustonConfigParameters.perform_patch(args, obj=None)
        return response


@api.route('/detection')
class DetectionConfig(Resource):
    """
    Detection pipeline configurations
    """

    def get(self):
        """
        Returns a json describing the available detectors for the frontend to
        provide users with options
        """
        ia_config_reader = IaConfig()
        detection_config = ia_config_reader.get_detect_model_frontend_data()
        success = detection_config is not None
        response = {'detection_config': detection_config, 'success': success}

        return response
