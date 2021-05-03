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

        data = {}
        # data.update(request.args)
        # data.update(args)
        try:
            data_ = json.loads(request.data)
            data.update(data_)
        except Exception:
            pass

        response = current_app.edm.request_passthrough(
            'encounter.data', 'post', {'data': data}, ''
        )

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
