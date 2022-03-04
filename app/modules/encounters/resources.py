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
from flask import request, current_app, make_response

from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException

from app.extensions.api import abort

from . import parameters, schemas
from .models import Encounter
import app.extensions.logging as AuditLog


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
        if not response.get('success', False):
            return response

        edm_json = response['result']

        schema = schemas.AugmentedEdmEncounterSchema()
        edm_json.update(schema.dump(encounter).data)
        # EDM uses id, houston API is all guid so ditch the id
        edm_json.pop('id', None)
        return edm_json

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['encounter'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['encounters:write'])
    @api.parameters(parameters.PatchEncounterDetailsParameters())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, encounter):
        """
        Patch Encounter details by ID.
        """
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()
        edm_args = [
            arg
            for arg in args
            if arg.get('path')
            in parameters.PatchEncounterDetailsParameters.PATH_CHOICES_EDM
        ]
        houston_args = [
            arg
            for arg in args
            if arg.get('path')
            in parameters.PatchEncounterDetailsParameters.PATH_CHOICES_HOUSTON
        ]

        if edm_args:
            log.debug(f'wanting to do edm patch on args={edm_args}')
            try:
                result_data = current_app.edm.request_passthrough_result(
                    'encounter.data',
                    'patch',
                    {'data': edm_args},
                    encounter.guid,
                    request_headers=request.headers,
                )
                # EDM uses id, houston API is all guid so ditch the id
                result_data.pop('id', None)

            except HoustonException as ex:
                if isinstance(ex.message, dict):
                    message = ex.message.get('details', ex.message)
                else:
                    message = ex.message
                abort(
                    ex.status_code,
                    message,
                    error=ex.get_val('error', 'Error'),
                )
        else:
            # this mimics output format of edm-patching
            result_data = {
                'version': encounter.version,
            }

        if houston_args:
            if not edm_args:
                # regular houston-patching
                context = api.commit_or_abort(
                    db.session,
                    default_error_message='Failed to update Encounter details.',
                )
            else:
                # irregular houston-patching, where we need to report that EDM data was set if houston setting failed
                context = api.commit_or_abort(
                    db.session,
                    default_error_message='Failed to update Encounter details.',
                    code=417,  # Arbitrary choice (Expectation Failed)
                    fields_written=edm_args,
                )

            with context:
                try:
                    parameters.PatchEncounterDetailsParameters.perform_patch(
                        houston_args, encounter
                    )
                except HoustonException as ex:
                    abort(ex.status_code, ex.message)
                db.session.merge(encounter)

            schema = schemas.AugmentedEdmEncounterSchema()
            result_data.update(schema.dump(encounter).data)

        if edm_args:
            # edm patch was successful
            new_version = result_data.get('version', None)
            if new_version is not None:
                encounter.version = new_version
                context = api.commit_or_abort(
                    db.session,
                    default_error_message='Failed to update Encounter version.',
                )
                with context:
                    db.session.merge(encounter)
            # rtn['_patchResults'] = rdata.get('patchResults', None)  # FIXME i think this gets lost cuz not part of results_data

        AuditLog.patch_object(log, encounter, args, duration=timer.elapsed())
        schema = schemas.AugmentedEdmEncounterSchema()
        result_data.update(schema.dump(encounter).data)
        return result_data

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
        response = None
        try:
            (response, response_data, result) = encounter.delete_from_edm(
                current_app, request
            )
        except HoustonException as ex:
            edm_status_code = ex.get_val('edm_status_code', 400)
            log.warning(
                f'Encounter.delete {encounter.guid} failed: ({ex.status_code} / edm={edm_status_code}) {ex.message}'
            )
            response_data = ex.get_val('response_data', {})
            abort(
                400,
                'Delete failed',
                vulnerableIndividualGuid=response_data.get('vulnerableIndividual'),
                vulnerableSightingGuid=response_data.get('vulnerableSighting'),
            )

        # we have to roll our own response here (to return) as it seems the only way we can add a header
        #   (which we are using to denote the encounter DELETE also triggered a sighting DELETE, since
        #   no body is returned on a 204 for DELETE
        resp = make_response()
        resp.status_code = 204
        sighting_id = None
        deleted_individuals = None
        if result is not None:
            sighting_id = result.get('deletedSighting', None)
            deleted_individuals = result.get('deletedIndividuals', None)
        if sighting_id is not None:
            from app.modules.sightings.models import Sighting

            sighting = Sighting.query.get(sighting_id)
            if sighting is None:
                log.error(
                    f'deletion of {encounter} triggered deletion of sighting {sighting_id}; but this was not found!'
                )
                abort(400, f'Cascade-deleted Sighting not found id={sighting_id}')
            else:
                log.warning(  # TODO future audit log here
                    f'EDM triggered self-deletion of {sighting} result={result}'
                )
                sighting.delete_cascade()  # this will get rid of our encounter(s) as well so no need to encounter.delete()
                resp.headers['x-deletedSighting-guid'] = sighting_id
        else:
            encounter.delete()
        # TODO handle failure of feather deletion (when edm successful!)  out-of-sync == bad
        if deleted_individuals:
            from app.modules.individuals.models import Individual

            deleted_ids = []
            for indiv_guid in deleted_individuals:
                goner = Individual.query.get(indiv_guid)
                if goner is None:
                    log.error(
                        f'EDM requested cascade-delete of individual id={indiv_guid}; but was not found in houston!'
                    )
                else:
                    log.info(f'EDM requested cascade-delete of {goner}; deleting')
                    deleted_ids.append(indiv_guid)
                    goner.delete()

            resp.headers['x-deletedIndividual-guids'] = ', '.join(deleted_ids)
        return resp


@api.route('/debug/<uuid:encounter_guid>', doc=False)
@api.login_required(oauth_scopes=['encounters:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Encounter not found.',
)
@api.resolve_object_by_model(Encounter, 'encounter')
class EncounterDebugByID(Resource):
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['encounter'],
            'action': AccessOperation.READ_DEBUG,
        },
    )
    def get(self, encounter):
        return encounter.sighting.get_debug_sighting_json()
