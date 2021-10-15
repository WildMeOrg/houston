# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Configuration resources
--------------------------
"""

import logging

from flask_login import current_user  # NOQA
from flask import current_app, request
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus
from app.extensions.api import Namespace, abort

from app.modules.users.models import User
from app.modules.site_settings.models import SiteSetting

import json


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
edm_configuration = Namespace(
    'configuration', description='(EDM) Configuration'
)  # pylint: disable=invalid-name
edm_configurationDefinition = Namespace(
    'configurationDefinition', description='(EDM) Configuration Definition'
)  # pylint: disable=invalid-name


SITESETTINGS_TO_APPEND = (
    'email_service',
    'email_service_username',
    'email_service_password',
    'email_default_sender_email',
    'email_default_sender_name',
)


@edm_configurationDefinition.route('/<string:target>/<path:path>')
# @edm_configurationDefinition.login_required(oauth_scopes=['configuration:read'])
class EDMConfigurationDefinition(Resource):
    """
    Configuration Definitions
    """

    def get(self, target, path):
        data = current_app.edm.get_dict(
            'configurationDefinition.data',
            path,
            target=target,
        )
        from app.modules.ia_config_reader import IaConfig

        species_json = None
        if path == '__bundle_setup':
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

        if path == '__bundle_setup':
            data = _site_setting_get_definition_inject(data)

        # TODO also traverse private here FIXME
        return data


@edm_configuration.route('/<string:target>', defaults={'path': ''}, doc=False)
@edm_configuration.route('/<string:target>/<path:path>')
# @edm_configuration.login_required(oauth_scopes=['configuration:read'])
class EDMConfiguration(Resource):
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

    def get(self, target, path):
        params = {}
        params.update(request.args)
        params.update(request.form)

        data = current_app.edm.get_dict(
            'configuration.data',
            path,
            target=target,
        )

        user_is_admin = (
            current_user is not None
            and not current_user.is_anonymous
            and current_user.is_admin
        )

        if path == '__bundle_setup':
            data['response']['configuration'][
                'site.adminUserInitialized'
            ] = User.admin_user_initialized()
            site_settings = SiteSetting.query.filter_by(public=True).order_by('key')
            ss_json = {}
            for ss in site_settings:
                if ss.file_upload is not None:
                    ss_json[
                        ss.key
                    ] = f'/api/v1/fileuploads/src/{str(ss.file_upload.guid)}'
            data['response']['configuration']['site.images'] = ss_json
            data = _site_setting_get_inject(data)
            data = _security_scrub_bundle(data, user_is_admin)
        elif (
            'response' in data
            and data['response'].get('private', False)
            and not user_is_admin
        ):
            log.warn(f'blocked configuration {path} private=true for unauthorized user')
            abort(code=HTTPStatus.FORBIDDEN, message='unavailable')

        return data

    @edm_configuration.login_required(oauth_scopes=['configuration:write'])
    def post(self, target, path):
        data = {}
        data.update(request.args)
        data.update(request.form)
        try:
            data_ = json.loads(request.data)
            data.update(data_)
        except Exception:
            pass

        success_ss_keys = _process_site_settings(data)
        passthrough_kwargs = {'data': data}

        files = request.files
        if len(files) > 0:
            passthrough_kwargs['files'] = files

        response = current_app.edm.request_passthrough(
            'configuration.data', 'post', passthrough_kwargs, path, target
        )
        if not response.ok:
            return response
        res = response.json()
        if 'updated' in res:
            res['updated'].extend(success_ss_keys)
        return res

    @edm_configuration.login_required(oauth_scopes=['configuration:write'])
    def patch(self, target, path):
        data = {}
        try:
            data = json.loads(request.data)
        except Exception:
            pass

        passthrough_kwargs = {'data': data}
        response = current_app.edm.request_passthrough(
            'configuration.data', 'patch', passthrough_kwargs, path, target
        )

        return response


def _site_setting_get_inject(data):
    assert 'response' in data and 'configuration' in data['response']
    for sskey in SITESETTINGS_TO_APPEND:
        val = SiteSetting.get_string(sskey)
        if val is None:
            data['response']['configuration'][sskey] = {
                'id': sskey,
                'isSiteSetting': True,
                'value': '',
                'valueNotSet': True,
            }
        else:
            data['response']['configuration'][sskey] = {
                'id': sskey,
                'isSiteSetting': True,
                'value': val,
            }
        if sskey == 'email_service_password':
            data['response']['configuration'][sskey]['private'] = True
    return data


def _site_setting_get_definition_inject(data):
    assert 'response' in data and 'configuration' in data['response']
    for sskey in SITESETTINGS_TO_APPEND:
        data['response']['configuration'][sskey] = {
            'defaultValue': '',
            'isPrivate': False,
            'settable': True,
            'fieldType': 'string',
            'displayType': 'string',
        }
        val = SiteSetting.get_string(sskey)
        if val is not None:
            data['response']['configuration'][sskey]['currentValue'] = val
        if sskey == 'email_service_password':
            data['response']['configuration'][sskey]['isPrivate'] = True
            del data['response']['configuration'][sskey]['currentValue']
        if sskey == 'email_service':
            data['response']['configuration'][sskey]['defaultValue'] = None
            data['response']['configuration'][sskey]['options'] = [None, 'mailchimp']
    return data


def _security_scrub_bundle(data, has_admin):
    assert 'response' in data and 'configuration' in data['response']
    delete_keys = []
    for key in data['response']['configuration'].keys():
        if not isinstance(data['response']['configuration'][key], dict):
            continue
        if not data['response']['configuration'][key].get('private', False):
            continue
        if has_admin:
            log.debug(f'admin access given to private key={key} in bundle')
        else:
            delete_keys.append(key)
    for key in delete_keys:
        del data['response']['configuration'][key]
    return data


def _process_site_settings(data):
    assert isinstance(data, dict)
    from app.modules.site_settings.models import EDM_PREFIX

    delete_keys = []
    success_keys = []
    for key in data.keys():
        if key.startswith(EDM_PREFIX):
            continue
        delete_keys.append(key)
        if key not in SITESETTINGS_TO_APPEND:
            log.info(f'skipping unrecognized SiteSetting key={key}')
            continue
        if not isinstance(data[key], str):
            log.warning(
                f'skipping unrecognized SiteSetting key={key}, value is not string; value={data[key]}'
            )
            abort(
                code=HTTPStatus.BAD_REQUEST,
                message=f'key={key} currently can only be passed a string',
            )
        log.debug(f'bundle updating SiteSetting key={key}')
        public = not key.startswith('email_service')
        SiteSetting.set(key, string=data[key], public=public)
        success_keys.append(key)
    for key in delete_keys:
        del data[key]
    return success_keys
