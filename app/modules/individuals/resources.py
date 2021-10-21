# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Individuals resources
--------------------------
"""

import logging
import json
from flask_restx_patched import Resource
from app.extensions.api import abort
from flask_restx._http import HTTPStatus
from flask import request, current_app
from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException

from . import parameters, schemas
from .models import Individual
import app.extensions.logging as AuditLog

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('individuals', description='Individuals')  # pylint: disable=invalid-name


class IndividualCleanup(object):
    def __init__(self):
        self.individual_guid = None

    def rollback_and_abort(self, message='Unknown Error', code=400):
        if self.individual_guid is not None:
            failed_individual = Individual.query.get(self.individual_guid)
            if failed_individual is not None:
                with db.session.begin():
                    try:
                        failed_individual.delete_from_edm(current_app)
                    except Exception:
                        pass
                    db.session.delete(failed_individual)

                log.error(
                    'The Individual with guid %r was not persisted to the EDM and has been deleted from Houston'
                    % self.individual_guid
                )
        abort(
            success=False,
            passed_message=message,
            message='Error',
            code=code,
        )


@api.route('/')
@api.login_required(oauth_scopes=['individuals:read'])
class Individuals(Resource):
    """
    Manipulations with Individuals.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Individual,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseIndividualSchema(many=True))
    def get(self, args):
        """
        List of Individual.

        Returns a list of Individual starting from ``offset`` limited by ``limit``
        parameter.
        """
        return Individual.query.offset(args['offset']).limit(args['limit'])

    @api.login_required(oauth_scopes=['individuals:write'])
    @api.parameters(parameters.CreateIndividualParameters())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Individual.
        """
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        cleanup = IndividualCleanup()

        request_in = {}
        try:
            request_in_ = json.loads(request.data)
            request_in.update(request_in_)
        except Exception:
            pass

        if (
            'encounters' not in request_in
            or not isinstance(request_in['encounters'], list)
            or len(request_in['encounters']) < 1
        ):
            cleanup.rollback_and_abort(message='No Encounters in POST')

        from app.modules.encounters.models import Encounter

        for enc_json in request_in['encounters']:
            if enc_json['id'] is not None:
                encounter = Encounter.query.get(enc_json['id'])
                if encounter is not None and encounter.individual_guid is not None:
                    cleanup.rollback_and_abort(
                        message='Individual POST included an encounter that already has an Individual.'
                    )
        try:
            result_data = current_app.edm.request_passthrough_result(
                'individual.data', 'post', {'data': request_in}, ''
            )
        except HoustonException as ex:
            cleanup.rollback_and_abort(ex.message)

        # if you get 'success' back and there is no id, we have problems indeed
        if result_data['id'] is not None:
            cleanup.individual_guid = result_data['id']
        else:
            cleanup.rollback_and_abort(
                message='Individual.post: Improbable error. success=True but no Individual id in response.'
            )

        if 'encounters' in request_in and 'encounters' not in result_data:
            cleanup.rollback_and_abort(
                message='Individual.post: request_in had an encounters list, but result_data did not.'
            )

        if not len(request_in['encounters']) == len(result_data['encounters']):
            cleanup.rollback_and_abort(
                message='Individual.post: Imbalance in encounters between request_in and result_data.'
            )

        encounters = []

        for result_encounter_json in request_in['encounters']:
            result_encounter = Encounter.query.get(result_encounter_json['id'])
            if result_encounter is not None:
                encounters.append(result_encounter)
            else:
                log.error(
                    'Individual.post: at least one encounter found in request_in or result_data was not found in the Houston database. Aborting Individual creation.'
                )
                cleanup.rollback_and_abort(
                    message='Encounter(s) in request or response not in Houston db.',
                    code=500,
                )

        # finally make the Individual if all encounters are found
        individual = Individual(
            guid=result_data['id'],
            encounters=encounters,
            version=result_data.get('version'),
        )
        AuditLog.user_create_object(log, individual, duration=timer.elapsed())
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Individual'
        )

        with context:
            db.session.add(individual)
        db.session.refresh(individual)

        rtn = {
            'success': True,
            'result': {
                'id': str(individual.guid),
                'version': individual.version,
                'encounters': result_data['encounters'],
            },
        }

        return rtn


@api.route('/<uuid:individual_guid>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Individual not found.',
)
@api.resolve_object_by_model(Individual, 'individual')
class IndividualByID(Resource):
    """
    Manipulations with a specific Individual.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['individual'],
            'action': AccessOperation.READ,
        },
    )
    def get(self, individual):
        """
        Get Individual details by ID.
        """
        if individual is not None:
            log.info(
                'GET passthrough called for Individual with GUID: %r ', individual.guid
            )
        else:
            log.error('GET passthrough called for nonexistent Individual')

        from app.modules.individuals.schemas import DetailedIndividualSchema

        rtn_json = current_app.edm.get_dict('individual.data_complete', individual.guid)
        schema = DetailedIndividualSchema(many=False)
        rtn_json.update(schema.dump(individual).data)

        return rtn_json

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['individual'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.parameters(parameters.PatchIndividualDetailsParameters())
    @api.response(schemas.DetailedIndividualSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, individual):
        """
        Patch Individual details by ID.
        """
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Individual details.'
        )

        # If value for /encounters is not a list, make it into a list
        for arg in args:
            if arg['path'] == '/encounters' and isinstance(arg['value'], str):
                arg['value'] = [arg['value']]

        houston_args = [
            arg
            for arg in args
            if arg['path']
            in parameters.PatchIndividualDetailsParameters.PATH_CHOICES_HOUSTON
        ]

        with context:
            parameters.PatchIndividualDetailsParameters.perform_patch(
                houston_args, obj=individual
            )

        edm_args = [
            arg
            for arg in args
            if arg['path'] in parameters.PatchIndividualDetailsParameters.PATH_CHOICES_EDM
        ]

        if len(edm_args) > 0 and len(edm_args) != len(args):
            log.error(f'Mixed edm/houston patch called with args {args}')
            abort(
                success=False,
                passed_message='Cannot mix EDM patch paths and houston patch paths',
                message='Error',
                code=400,
            )

        if len(edm_args) > 0:
            log.debug(f'wanting to do edm patch on args={args}')
            result = None
            try:
                (
                    response,
                    response_data,
                    result,
                ) = current_app.edm.request_passthrough_parsed(
                    'individual.data',
                    'patch',
                    {'data': edm_args},
                    individual.guid,
                    request_headers=request.headers,
                )
            except HoustonException as ex:
                edm_status_code = ex.get_val('edm_status_code', 400)
                abort(
                    success=False,
                    passed_message=ex.message,
                    code=ex.status_code,
                    edm_status_code=edm_status_code,
                )

            # TODO handle individual deletion if last encounter removed

        db.session.merge(individual)
        AuditLog.patch_object(log, individual, args, duration=timer.elapsed())
        return individual

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['individual'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, individual):
        """
        Delete an Individual by ID.
        """
        response = individual.delete_from_edm()
        if response.ok:
            response_data = response.json()
        if not response.ok or not response_data.get('success', False):
            log.warning(
                'Individual.delete:  Failed to delete id %r using delete_from_edm(). response_data=%r'
                % (individual.guid, response_data)
            )
        try:
            individual.delete()
        except Exception:
            abort(
                success=False, passed_message='Delete failed', message='Error', code=400
            )

        return None


@api.route('/<uuid:individual_guid>/cooccurrence')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Individual not found.',
)
@api.resolve_object_by_model(Individual, 'individual')
@api.response(schemas.BaseIndividualSchema(many=True))
class IndividualByIDCoOccurence(Resource):
    """
    List co-occurring individuals
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['individual'],
            'action': AccessOperation.READ,
        },
    )
    def get(self, individual):
        if individual is not None:
            others = individual.get_cooccurring_individuals()
            return others
