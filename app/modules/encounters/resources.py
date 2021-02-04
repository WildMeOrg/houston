# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Encounters resources
--------------------------
"""

import logging

from flask_login import current_user  # NOQA
from flask_restplus_patched import Resource
from flask_restplus._http import HTTPStatus
from flask import request, current_app

from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation

from werkzeug.exceptions import BadRequest
from app.extensions.api import abort

import json


from . import parameters, schemas
from .models import Encounter


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('encounters', description='Encounters')  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['encounters:read'])
class Encounters(Resource):
    """
    Manipulations with Encounters.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Encounter,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseEncounterSchema(many=True))
    def get(self, args):
        """
        List of Encounter.

        Returns a list of Encounter starting from ``offset`` limited by ``limit``
        parameter.
        """
        return Encounter.query.offset(args['offset']).limit(args['limit'])

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Encounter,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['encounters:write'])
    @api.parameters(parameters.CreateEncounterParameters())
    # @api.response(schemas.DetailedEncounterSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Encounter.
        """

        data = {}
        # data.update(request.args)
        # data.update(args)
        try:
            data_ = json.loads(request.data)
            data.update(data_)
        except Exception:
            pass

        target = 'default'
        path = ''
        request_func = current_app.edm.post_passthrough
        passthrough_kwargs = {'data': data}
        response = _request_passthrough(target, path, request_func, passthrough_kwargs)

        response_data = None
        result_data = None
        if response.ok:
            response_data = response.json()
            result_data = response_data.get('result', None)

        if (
            not response.ok
            or not response_data.get('success', False)
            or result_data is None
        ):
            log.warning('Encounter.post failed')
            passed_message = {'message': {'key': 'error'}}
            if response_data is not None and 'message' in response_data:
                passed_message = response_data['message']
            abort(success=False, passed_message=passed_message, message='Error', code=400)

        # if we get here, edm has made the encounter, now we create & persist the feather model in houston

        assets = []
        from app.modules.assets.models import Asset

        if 'assets' in data and isinstance(data['assets'], list):
            for asset_data in data['assets']:
                if isinstance(asset_data, dict) and 'guid' in asset_data:
                    asset = Asset.find(asset_data['guid'])
                    if asset is not None:
                        assets.append(asset)

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Encounter'
        )
        with context:
            # TODO other houston-based relationships: orgs, projects, etc
            owner_guid = None
            pub = True  # legit? public if no owner?
            if current_user is not None:
                owner_guid = current_user.guid
                pub = False
            encounter = Encounter(
                guid=result_data['id'],
                version=result_data.get('version', 2),
                owner_guid=owner_guid,
                public=pub,
            )
            for asset in assets:
                encounter.add_asset_in_context(asset)
            db.session.add(encounter)
        log.debug('Encounter.post created edm/houston guid=%r' % (encounter.guid,))
        rtn = {
            'success': True,
            'result': {
                'guid': str(encounter.guid),
                'version': encounter.version,
            },
        }
        return rtn


@api.route('/<uuid:encounter_guid>')
@api.login_required(oauth_scopes=['encounters:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Encounter not found.',
)
@api.resolve_object_by_model(Encounter, 'encounter')
class EncounterByID(Resource):
    """
    Manipulations with a specific Encounter.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['encounter'],
            'action': AccessOperation.READ,
        },
    )
    def get(self, encounter):
        """
        Get Encounter full details by ID.
        """

        if encounter is not None:
            print('####### found encounter within houston : %s' % (encounter,))
            # note: should probably _still_ check edm for: stale cache, deletion!
            #      user.edm_sync(version)
            # return encounter
            # return True

        response = current_app.edm.get_encounter_data_dict(encounter.guid)
        # TODO handle non-200 ?
        # assert response.success
        if len(encounter.assets) > 0:
            from app.modules.assets.schemas import DetailedAssetSchema

            sch = DetailedAssetSchema(many=False, only=('guid', 'filename', 'src'))
            response['result']['assets'] = []
            for asset in encounter.get_assets():
                json, err = sch.dump(asset)
                response['result']['assets'].append(json)

        return response['result']

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['encounter'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['encounters:write'])
    @api.parameters(parameters.PatchEncounterDetailsParameters())
    @api.response(schemas.DetailedEncounterSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, encounter):
        """
        Patch Encounter details by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Encounter details.'
        )
        with context:
            parameters.PatchEncounterDetailsParameters.perform_patch(args, obj=encounter)
            db.session.merge(encounter)
        return encounter

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['encounter'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['encounters:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, encounter):
        """
        Delete a Encounter by ID.
        """

        # first try delete on edm
        target = 'default'
        path = str(encounter.guid)
        request_func = current_app.edm.delete_passthrough
        passthrough_kwargs = {}
        response = _request_passthrough(target, path, request_func, passthrough_kwargs)

        response_data = None
        result_data = None
        if response.ok:
            response_data = response.json()
            result_data = response_data.get('result', None)

        if (
            not response.ok
            or not response_data.get('success', False)
            or result_data is None
        ):
            log.warning('Encounter.delete %r failed' % (encounter.guid))
            passed_message = {'message': {'key': 'error'}}
            if response_data is not None and 'message' in response_data:
                passed_message = response_data['message']
            abort(success=False, passed_message=passed_message, message='Error', code=400)

        # if we get here, edm has deleted the encounter, now houston feather
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to delete the Encounter.'
        )
        # TODO handle failure of feather deletion (when edm successful!)  out-of-sync == bad
        with context:
            db.session.delete(encounter)
        return None


def _request_passthrough(target, path, request_func, passthrough_kwargs):
    try:
        # Try to convert string integers to integers
        target = int(target)
    except ValueError:
        pass

    # Check target
    current_app.edm.ensure_initialed()
    targets = list(current_app.edm.targets)
    if target not in targets:
        raise BadRequest('The specified target %r is invalid.' % (target,))

    endpoint_url_ = current_app.edm.get_target_endpoint_url(target)
    endpoint = '%s/api/v0/org.ecocean.Encounter/%s' % (
        endpoint_url_,
        path,  # note path
    )

    headers = passthrough_kwargs.get('headers', {})
    allowed_header_key_list = [
        'Accept',
        'Content-Type',
        'User-Agent',
    ]
    is_json = False
    for header_key in allowed_header_key_list:
        header_value = request.headers.get(header_key, None)
        header_existing = headers.get(header_key, None)
        if header_value is not None and header_existing is None:
            headers[header_key] = header_value

        if header_key == 'Content-Type':
            if header_value is not None:
                if header_value.lower().startswith(
                    'application/javascript'
                ) or header_value.lower().startswith('application/json'):
                    is_json = True
    passthrough_kwargs['headers'] = headers

    if is_json:
        data_ = passthrough_kwargs.pop('data', None)
        if data_ is not None:
            passthrough_kwargs['json'] = data_

    response = request_func(
        None,
        endpoint=endpoint,
        target=target,
        decode_as_object=False,
        decode_as_dict=False,
        passthrough_kwargs=passthrough_kwargs,
    )
    return response
