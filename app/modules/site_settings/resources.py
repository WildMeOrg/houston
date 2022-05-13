# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Site Settings resources
--------------------------
"""

import logging
from pathlib import Path

from flask_login import current_user  # NOQA
from flask import current_app, request, redirect, url_for
from flask_restx_patched import Resource
from flask_restx._http import HTTPStatus

from app.extensions import db, is_extension_enabled
import app.extensions.logging as AuditLog  # NOQA
from app.extensions.api import abort, Namespace
from app.modules.users.models import User
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException
import app.version

from . import schemas, parameters
from .models import SiteSetting
import json


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace(
    'site-settings', description='Site Settings'
)  # pylint: disable=invalid-name


@api.route('/file')
@api.login_required(oauth_scopes=['site-settings:read'])
class SiteSettingFile(Resource):
    """
    Manipulations with File.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': SiteSetting,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseSiteSettingFileSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Files.
        """
        query = SiteSetting.query_search(args=args)
        query = query.filter(SiteSetting.file_upload_guid.isnot(None))
        return query

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': SiteSetting,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['site-settings:write'])
    @api.parameters(parameters.CreateSiteSettingFileParameters())
    @api.response(schemas.DetailedSiteSettingFileSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create or update a File.
        """
        from app.modules.fileuploads.models import FileUpload

        if args.get('transactionId'):
            transaction_id = args.pop('transactionId')
            if args.get('transactionPath'):
                paths = [args.pop('transactionPath')]
            else:
                paths = None
            fups = (
                FileUpload.create_fileuploads_from_tus(transaction_id, paths=paths) or []
            )
            if len(fups) != 1:
                # Delete the files in the filesystem
                # Can't use .delete() because fups are not persisted
                for fup in fups:
                    path = Path(fup.get_absolute_path())
                    if path.exists():
                        path.unlink()

                abort(
                    code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    message=f'Transaction {transaction_id} has {len(fups)} files, need exactly 1.',
                )
            with db.session.begin():
                db.session.add(fups[0])
            args['file_upload_guid'] = fups[0].guid
        elif not args.get('file_upload_guid'):
            abort(400, 'The File API should only be used for manipulating files')

        site_setting = SiteSetting.set(**args)
        message = f'{SiteSetting.__name__} file created with file guid:{site_setting.file_upload_guid}'
        AuditLog.audit_log(log, message)
        return site_setting


@api.route('/file/<string:file_key>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='File not found.',
)
@api.resolve_object_by_model(SiteSetting, 'file', 'file_key')
class SiteSettingFileByKey(Resource):
    """
    Manipulations with a specific File.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['file'],
            'action': AccessOperation.READ,
        },
    )
    def get(self, file):
        """
        Get File details by ID.
        """
        if file.file_upload_guid:
            return redirect(
                url_for(
                    'api.fileuploads_file_upload_src_u_by_id_2',
                    fileupload_guid=file.file_upload_guid,
                )
            )
        else:
            abort(400, 'File endpoint only for manipulation of files')

        schema = schemas.DetailedSiteSettingFileSchema()
        json_msg, err = schema.dump(file)
        return json_msg

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['file'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['site-settings:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, file):
        """
        Delete a File by ID.
        """
        AuditLog.audit_log(log, f'Deleting file {file}')
        context = api.commit_or_abort(
            db.session,
            default_error_message=f'Failed to delete the SiteSetting "{file.key}".',
        )
        with context:
            db.session.delete(file)
        return None


@api.route('/definition/main/<path:path>')
class MainConfigurationDefinition(Resource):
    """
    Site Setting Definitions
    """

    def _insert_houston_definitions(self, data):
        for key in SiteSetting.get_setting_keys():
            data['response']['configuration'][
                key
            ] = SiteSetting.get_as_edm_definition_format(key)
        return data

    def get(self, path):
        if not is_extension_enabled('edm'):
            data = {'response': {'configuration': {}}}
            return self._insert_houston_definitions(data)

        data = SiteSetting.get_edm_configuration_as_edm_format(
            'configurationDefinition.data', path
        )

        from app.modules.ia_config_reader import IaConfig

        species_json = None
        if SiteSetting.is_block_key(path):
            species_json = data['response']['configuration']['site.species']
        elif path == 'site.species':
            species_json = data['response']
        if species_json is not None:
            ia_config_reader = IaConfig()
            species = ia_config_reader.get_configured_species()
            if not isinstance(species_json['suggestedValues'], list):
                species_json['suggestedValues'] = ()
            for (
                sn
            ) in species:  # only adds a species that is not already in suggestedValues
                needed = True
                for sv in species_json['suggestedValues']:
                    if sv.get('scientificName', None) == sn:
                        needed = True
                if needed:
                    details = ia_config_reader.get_frontend_species_summary(sn)
                    if details is None:
                        details = {}
                    species_json['suggestedValues'].insert(
                        0,
                        {
                            'scientificName': sn,
                            'commonNames': [details.get('common_name', sn)],
                            'itisTsn': details.get('itis_id'),
                        },
                    )

        if SiteSetting.is_block_key(path):
            data = self._insert_houston_definitions(data)

        # TODO also traverse private here FIXME
        return data


@api.route('/main/<path:path>')
@api.route('/main', defaults={'path': ''}, doc=False)
class MainConfiguration(Resource):
    r"""
    A pass-through allows a GET or POST request to be referred to a registered back-end EDM

    CommandLine:
        EMAIL='test@localhost'
        PASSWORD='test'
        TIMESTAMP=$(date '+%Y%m%d-%H%M%S%Z')
        curl \
            -X POST \
            -c cookie.jar \
            -H 'Content-Type: multipart/form-data' \
            -H 'Accept: application/json' \
            -F email=${EMAIL} \
            -F password=${PASSWORD} \
            https://wildme.ngrok.io/api/v1/auth/sessions | jq
        curl \
            -X GET \
            -b cookie.jar \
            https://wildme.ngrok.io/api/v1/users/me | jq
        curl \
            -X POST \
            -b cookie.jar \
            -H 'Content-type: application/javascript' \
            -d "{\"site.name\": \"value-updated-${TIMESTAMP}\"}" \
            https://wildme.ngrok.io/api/v1/configuration/default/api/v0/configuration | jq
        curl \
            -X GET \
            -b cookie.jar \
            https://wildme.ngrok.io/api/v1/configuration/edm/default/api/v0/configuration/site.name | jq ".response.value"
    """

    def get(self, path):
        params = {}
        params.update(request.args)
        params.update(request.form)
        if path and path in SiteSetting.get_setting_keys():
            # Houston only key is a special case and we need to construct the response by hand
            data = {
                'success': True,
                'response': {
                    'configuration': {
                        path: SiteSetting.get_as_edm_format(path),
                    }
                },
            }
            return data

        if is_extension_enabled('edm'):
            data = SiteSetting.get_edm_configuration_as_edm_format(
                'configuration.data', path
            )
        else:
            # If tried to set EDM value and we have no EDM, it's a failure
            data = {'success': False, 'response': {'configuration': {}}}

        user_is_admin = (
            current_user is not None
            and not current_user.is_anonymous
            and current_user.is_admin
        )

        if SiteSetting.is_block_key(path):
            data['response']['configuration'][
                'site.adminUserInitialized'
            ] = User.admin_user_initialized()
            houston_settings = SiteSetting.query.filter_by(public=True).order_by('key')
            ss_json = {}
            for ss in houston_settings:
                if ss.file_upload is not None:
                    ss_json[ss.key] = url_for(
                        'api.fileuploads_file_upload_src_u_by_id_2',
                        fileupload_guid=str(ss.file_upload.guid),
                        _external=False,
                    )
            data['response']['configuration']['site.images'] = ss_json

            for key, type_def in SiteSetting.HOUSTON_SETTINGS.items():
                key_data = SiteSetting.get_as_edm_format(key)
                if user_is_admin or type_def.get('public', True):
                    data['response']['configuration'][key] = key_data
        elif (
            'response' in data
            and data['response'].get('private', False)
            and not user_is_admin
        ):
            log.warning(
                f'blocked configuration {path} private=true for unauthorized user'
            )
            abort(HTTPStatus.FORBIDDEN, 'unavailable')

        return data

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': SiteSetting,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['site-settings:write'])
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

        success_ss_keys = []
        try:
            if path == '' or path == 'block':  # posting a bundle (no path)
                success_ss_keys = _process_houston_data(data)
            elif path in SiteSetting.get_setting_keys():
                if '_value' not in data.keys():
                    abort(400, 'Need _value as the key in the data setting')
                if data['_value'] is not None:
                    SiteSetting.set_key_value(path, data['_value'])
                else:
                    SiteSetting.forget_key_value(path)
                resp = {'success': True, 'key': path}
                return resp

        except HoustonException as ex:
            abort(ex.status_code, ex.message)

        passthrough_kwargs = {'data': data}

        files = request.files
        if len(files) > 0:
            passthrough_kwargs['files'] = files

        if is_extension_enabled('edm'):
            response = SiteSetting.post_edm_configuration(path, passthrough_kwargs)
            if not response.ok:
                return response
            res = response.json()
            if 'updated' in res:
                res['updated'].extend(success_ss_keys)
        else:
            res = {'success': False}

        message = f'Setting path:{path} to {data}'
        AuditLog.audit_log(log, message, duration=timer.elapsed())
        return res

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': SiteSetting,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['site-settings:write'])
    def patch(self, **kwargs):
        """
        Patch SiteSetting details.
        """
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()
        request_in_ = json.loads(request.data)
        for arg in request_in_:
            if arg['op'] == 'remove':
                try:
                    SiteSetting.forget_key_value(arg['path'])
                except HoustonException as ex:
                    abort(ex.status_code, ex.message)
            else:
                abort(400, f'op {arg["op"]} not supported on {arg["path"]}')

        message = f'Patching path:{kwargs["path"]} to {request_in_}'
        AuditLog.audit_log(log, message, duration=timer.elapsed())
        return {'success': True}

    @api.login_required(oauth_scopes=['site-settings:write'])
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, path):
        if SiteSetting.is_block_key(path):
            abort(400, 'Not permitted to delete entire config')
        AuditLog.audit_log(log, f'Deleting {path}')
        try:
            SiteSetting.forget_key_value(path)
        except HoustonException as ex:
            abort(ex.status_code, ex.message)
        return None


def _process_houston_data(data):
    assert isinstance(data, dict)
    delete_keys = []
    success_keys = []
    for key in data.keys():
        if SiteSetting.is_edm_key(key):
            continue

        delete_keys.append(key)
        if key not in SiteSetting.get_setting_keys():
            log.warning(f'skipping unrecognized Houston Setting key={key}')
            continue
        if data[key] is not None:
            SiteSetting.set_key_value(key, data[key])
        else:
            SiteSetting.forget_key_value(key)
        success_keys.append(key)

    for key in delete_keys:
        del data[key]
    return success_keys


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

        acm_version = current_app.acm.get_dict('version.dict', None)
        if isinstance(acm_version, dict):
            acm_version = acm_version['response']
        else:
            # acm returns a non 200 response
            acm_version = repr(acm_version)
        edm_version = current_app.edm.get_dict('version.dict', None)
        if not isinstance(edm_version, dict):
            # edm returns a non 200 response
            edm_version = repr(edm_version)
        return {
            'houston': {
                'version': app.version.version,
                'git_version': app.version.git_revision,
            },
            'acm': acm_version,
            'edm': edm_version,
        }


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


# The apiKeys for the frontend to read
@api.route('/apiKeys')
class ApiKeySettings(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': SiteSetting,
            'action': AccessOperation.READ,
        },
    )
    def get(self):
        return SiteSetting.get_apikeys_json()
