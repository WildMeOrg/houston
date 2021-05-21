# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Encounters resources
--------------------------
"""

import logging

from flask_login import current_user  # NOQA
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus
from flask import request, current_app

from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException

from app.extensions.api import abort

import json


from . import parameters, schemas
from .models import Encounter


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('encounters', description='Encounters')  # pylint: disable=invalid-name


@api.route('/')
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
    @api.login_required(oauth_scopes=['encounters:read'])
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseEncounterSchema(many=True))
    def get(self, args):
        """
        List of Encounter.

        Returns a list of Encounter starting from ``offset`` limited by ``limit``
        parameter.
        """
        return Encounter.query.offset(args['offset']).limit(args['limit'])

    # NOTE: question whether POST /encounter should be allowed at all, since it would be detached from a sighting!
    #       probably consider deprecating this
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Encounter,
            'action': AccessOperation.WRITE,
        },
    )
    @api.parameters(parameters.CreateEncounterParameters())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Encounter.
        """

        abort(
            success=False,
            message='Error: Encounter must be made as part of a Sighting via POST or PATCH',
            code=400,
        )

        data = {}
        # data.update(request.args)
        # data.update(args)
        try:
            data_ = json.loads(request.data)
            data.update(data_)
        except Exception:
            pass

        try:
            result_data = current_app.edm.request_passthrough_result(
                'encounter.data', 'post', {'data': data}, ''
            )
        except HoustonException as ex:
            abort(400, 'Error', success=False, passed_message=ex.message)

        # if we get here, edm has made the encounter, now we create & persist the feather model in houston

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new houston Encounter'
        )
        try:
            from app.modules.users.models import User

            owner_guid = User.get_public_user().guid
            with context:
                # TODO other houston-based relationships: orgs, projects, etc
                pub = True  # legit? public if no owner?
                if current_user is not None and not current_user.is_anonymous:
                    owner_guid = current_user.guid
                    pub = False
                encounter = Encounter(
                    guid=result_data['id'],
                    version=result_data.get('version', 2),
                    owner_guid=owner_guid,
                    public=pub,
                )
                db.session.add(encounter)
        except Exception as ex:
            log.error(
                'Encounter.post FAILED houston feather object creation guid=%r - will attempt to DELETE edm Encounter; (payload %r) ex=%r'
                % (
                    encounter.guid,
                    data,
                    ex,
                )
            )
            # clean up after ourselves by removing encounter from edm
            encounter.delete_from_edm(current_app)
            raise ex

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

        # note: should probably _still_ check edm for: stale cache, deletion!
        #      user.edm_sync(version)

        response = current_app.edm.get_dict('encounter.data_complete', encounter.guid)
        if not isinstance(response, dict):  # some non-200 thing, incl 404
            return response

        return encounter.augment_edm_json(response['result'])

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['encounter'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['encounters:write'])
    @api.parameters(parameters.PatchEncounterDetailsParameters())
    # @api.response(schemas.DetailedEncounterSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, encounter):
        """
        Patch Encounter details by ID.
        """

        edm_count = 0
        for arg in args:
            if (
                'path' in arg
                and arg['path']
                in parameters.PatchEncounterDetailsParameters.PATH_CHOICES_EDM
            ):
                edm_count += 1
        if edm_count > 0 and edm_count != len(args):
            log.error(f'Mixed edm/houston patch called with args {args}')
            abort(
                success=False,
                passed_message='Cannot mix EDM patch paths and houston patch paths',
                message='Error',
                code=400,
            )

        rdata = {}
        if edm_count > 0:
            log.debug(f'wanting to do edm patch on args={args}')
            headers = {
                'x-allow-delete-cascade-individual': request.headers.get(
                    'x-allow-delete-cascade-individual', 'false'
                ),
                'x-allow-delete-cascade-sighting': request.headers.get(
                    'x-allow-delete-cascade-sighting', 'false'
                ),
            }
            response = current_app.edm.request_passthrough(
                'encounter.data',
                'patch',
                {'data': args, 'headers': headers},
                encounter.guid,
            )
            rdata = response.json()
            if (
                not response.ok
                or response.status_code != 200
                or not rdata['success']
                or 'result' not in rdata
            ):
                code = response.status_code
                if code > 600:
                    code = 400  # flask doesnt like us to use "invalid" codes. :(
                log.warning(f'EDM patch got {response.status_code} response of {rdata}')
                abort(
                    success=False,
                    passed_message=rdata.get('message', 'unknown error'),
                    code=code,
                    edm_status_code=response.status_code,
                )

            # edm patch was successful
            new_version = rdata['result'].get('version', None)
            if new_version is not None:
                encounter.version = new_version
                context = api.commit_or_abort(
                    db.session,
                    default_error_message='Failed to update Encounter version.',
                )
                with context:
                    db.session.merge(encounter)
            return rdata

        # no EDM, so fall thru to regular houston-patching
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Encounter details.'
        )
        with context:
            parameters.PatchEncounterDetailsParameters.perform_patch(args, obj=encounter)
            db.session.merge(encounter)
        # this mimics output format of edm-patching
        return {
            'success': True,
            'result': {'id': str(encounter.guid), 'version': encounter.version},
        }

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
        response = encounter.delete_from_edm(current_app)
        response_data = None
        if response.ok:
            response_data = response.json()

        if not response.ok or not response_data.get('success', False):
            log.warning(
                'Encounter.delete %r failed: %r' % (encounter.guid, response_data)
            )
            abort(
                success=False, passed_message='Delete failed', message='Error', code=400
            )

        # if we get here, edm has deleted the encounter, now houston feather
        # TODO handle failure of feather deletion (when edm successful!)  out-of-sync == bad
        encounter.delete()
        return None
