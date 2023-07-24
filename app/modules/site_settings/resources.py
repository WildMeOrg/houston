# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Site Settings resources
--------------------------
"""

import json
import logging
from http import HTTPStatus

from flask import current_app, request
from flask_login import current_user  # NOQA

import app.extensions.logging as AuditLog  # NOQA
import app.version
from app.extensions import is_extension_enabled
from app.extensions.api import Namespace, abort
from app.modules import is_module_enabled
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException
from flask_restx_patched import Resource

from . import schemas
from .models import SiteSetting

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace(
    'site-settings', description='Site Settings'
)  # pylint: disable=invalid-name


@api.route('/data')
class MainDataBlock(Resource):
    """
    Site Setting Full block of data manipulations
    """

    def get(self):
        return SiteSetting.get_all_rest_definitions()

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': SiteSetting,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['site-settings:write'])
    def post(self):
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        data = {}
        data.update(request.args)
        data.update(request.form)
        try:
            data_ = json.loads(request.data)
            data.update(data_)
        except Exception:
            pass
        try:
            # Transitory, allow old and new (value) data format
            if 'value' in data.keys():
                log.debug('Site settings by value')
                SiteSetting.set_rest_block_data(data['value'])
            else:
                log.debug('Site settings without value')
                SiteSetting.set_rest_block_data(data)

        except HoustonException as ex:
            abort(ex.status_code, ex.message)

        message = f'Setting block data to {data}'
        AuditLog.audit_log(log, message, duration=timer.elapsed())
        return {}

    @api.login_required(oauth_scopes=['site-settings:write'])
    def patch(self, **kwargs):
        """
        Patch SiteSetting details.
        """
        from app.extensions.elapsed_time import ElapsedTime
        from app.modules.site_settings.helpers import SiteSettingCustomFields

        timer = ElapsedTime()
        request_in_ = json.loads(request.data)
        for arg in request_in_:
            if arg['op'] == 'remove':
                try:
                    if arg['path'] and arg['path'].startswith('site.custom.customField'):
                        SiteSettingCustomFields.patch_remove(
                            arg['path'], arg.get('force', False)
                        )
                    else:
                        SiteSetting.forget_key_value(arg['path'])
                except HoustonException as ex:
                    abort(ex.status_code, ex.message)
                except ValueError as ex:
                    abort(409, str(ex))
            else:
                abort(400, f'op {arg["op"]} not supported on {arg["path"]}')

        message = f'Patching path: {request_in_}'
        AuditLog.audit_log(log, message, duration=timer.elapsed())
        return {}


@api.route('/data/<path:path>')
class MainDataByPath(Resource):
    """
    Site Setting single item of data manipulations
    """

    # No permissions check as anonymous users need to be able to read sentryDsn
    # Also cannot use the resolve_object_by_model concept as the path can have a default value without being in
    # the database
    def get(self, path):
        try:
            return {'key': path, 'value': SiteSetting.get_rest_value(path)}
        except HoustonException as ex:
            abort(ex.status_code, ex.message)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': SiteSetting,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['site-settings:write'])
    @api.response(schemas.BaseSiteSettingSchema())
    def post(self, path):
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        data = {}
        data.update(request.args)
        data.update(request.form)
        try:
            data_ = json.loads(request.data)
            data.update(data_)
        except Exception:
            pass
        try:
            if SiteSetting.is_valid_setting(path):
                if 'value' not in data.keys():
                    abort(400, 'Need value as the key in the data setting')
                elif data['value'] is not None:
                    if SiteSetting.get_key_type(path) == 'file':
                        site_setting = SiteSetting.upload_file(path, data['value'])
                        message = f'{SiteSetting.__name__} file created with file guid:{site_setting.file_upload_guid}'
                    else:
                        site_setting = SiteSetting.set_key_value(path, data['value'])
                        message = f'Setting path: {path} to {data}'
                    AuditLog.audit_log(log, message, duration=timer.elapsed())
                    return site_setting
                else:
                    SiteSetting.forget_key_value(path)
                    return {'key': path}
            else:
                abort(400, f'{path} not supported')

        except HoustonException as ex:
            abort(ex.status_code, ex.message)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': SiteSetting,
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['site-settings:write'])
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, path):
        AuditLog.audit_log(log, f'Deleting {path}')
        try:
            SiteSetting.forget_key_value(path)
        except HoustonException as ex:
            abort(ex.status_code, ex.message)
        return None


@api.route('/detection')
class DetectionConfigs(Resource):
    """
    Detection pipeline configurations
    """

    def get(self):
        """
        Returns a json describing the available detectors for the frontend to
        provide users with options
        """
        from app.modules.ia_config_reader import IaConfig

        ia_config_reader = IaConfig()
        detection_config = ia_config_reader.get_detect_model_frontend_data()
        success = detection_config is not None
        response = {'detection_config': detection_config, 'success': success}
        log.debug(f'Detection config: {response}')

        return response


@api.route('/ia_classes')
class IaClassConfigs(Resource):
    """
    Configured IA classes
    """

    def get(self):
        """
        Returns a json describing the available detectors for the frontend to
        provide users with options
        """
        from app.modules.ia_config_reader import IaConfig

        ia_config_reader = IaConfig()
        ia_classes = ia_config_reader.get_all_ia_classes()
        success = ia_classes is not None
        response = {'ia_classes': ia_classes, 'success': success}

        return response


@api.route('/site-info')
class SiteInfo(Resource):
    def get(self):
        from flask_login import current_user  # NOQA

        sage_version = current_app.sage.get_dict('version.dict', None)
        if isinstance(sage_version, dict):
            sage_version = sage_version['response']['version']
        else:
            # sage returns a non 200 response
            sage_version = repr(sage_version)
        sage_uris = current_app.config.get('SAGE_URIS')
        default_sage_uri = ''

        # All users can get the site info but only staff users are permitted to see the Sage URI
        if current_user and not current_user.is_anonymous and current_user.is_staff:
            default_sage_uri = sage_uris.get('default')
        return {
            'houston': {
                'version': app.version.version,
                'git_version': app.version.git_revision,
            },
            'sage': {
                'version': sage_version,
                'uri': default_sage_uri,
            },
        }


@api.route('/public-data')
class PublicData(Resource):
    def get(self):

        response = {}

        if is_module_enabled('individuals'):
            from app.modules.individuals.models import Individual

            response['num_individuals'] = Individual.query_search().count()

        if is_module_enabled('sightings'):
            from app.modules.sightings.models import Sighting

            response['num_sightings'] = Sighting.query_search().count()

        if is_module_enabled('users'):
            from app.modules.users.models import User

            num_internal_users = User.query.filter(
                User.static_roles.op('&')(User.StaticRoles.INTERNAL.mask) > 1
            ).count()
            response['num_users'] = User.query_search().count() - num_internal_users

        if is_module_enabled('asset_groups'):
            from app.modules.asset_groups.models import (
                AssetGroupSighting,
                AssetGroupSightingStage,
            )

            response['num_pending_sightings'] = AssetGroupSighting.query.filter(
                AssetGroupSighting.stage != AssetGroupSightingStage.processed
            ).count()

        return response


@api.route('/heartbeat')
class SiteHeartbeat(Resource):
    def get(self):
        return {
            'version': app.version.version,
            'git_version': app.version.git_revision,
        }


# api path to do some general "is it working?" testing of site configuration, if desired
#   testing restricted to users with SiteSetting WRITE priveleges to protect abuse/leaks
@api.route('/test/<path:path>')
class TestSettings(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': SiteSetting,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['site-settings:write'])
    def get(self, path):

        if path.startswith('intelligent_agent_') and is_extension_enabled(
            'intelligent_agent'
        ):
            from app.extensions.intelligent_agent.models import IntelligentAgent

            name = path[18:]
            agent_cls = IntelligentAgent.get_agent_class_by_short_name(name)
            if not agent_cls:
                abort(400, f'Invalid Agent class {name}')
            try:
                agent = agent_cls()
                res = agent.test_setup()
            except Exception as ex:
                log.warning(f'test_setup() on {name} raised exception: {str(ex)}')
                abort(400, f'Test failure: {str(ex)}')
            log.info(f'/site-settings/test/{path} yielded {res}')
            if not res.get('success', False):
                abort(400, res.get('message', 'Unknown testing error'))
            # 200 only if we get success:True in response
            return res

        abort(400, 'Invalid test')
