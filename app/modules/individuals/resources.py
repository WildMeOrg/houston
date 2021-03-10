# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Individuals resources
--------------------------
"""

from app.extensions.api import abort
from flask_restx_patched import Resource
from flask_restx._http import HTTPStatus
from flask import request, current_app
from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation

from . import parameters, schemas
import logging
import json
from .models import Individual
from app.modules.encounters.models import Encounter

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('individuals', description='Individuals')  # pylint: disable=invalid-name


def _cleanup_post_and_abort(db, guid, message='Unknown error'):
    # if we fail, don't leave the Individual record anywhere TODO doublecheck EDM
    if guid is not None:
        failed_individual = Individual.query.get(guid)
        if failed_individual is not None:
            with db.session.begin():
                db.session.delete(failed_individual)
            log.error(
                'The Individual with guid %r was not successfully persisted to the EDM and has been deleted from Houston'
            )
        else:
            log.error(
                'Unexpected Error: The Individual with guid %r was not persisted to the EDM and could not be found in Houston'
            )
    abort(success=False, passed_message=message, message='Error', code=400)


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
    @api.response(schemas.DetailedIndividualSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Individual.
        """
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
            _cleanup_post_and_abort(
                None,
                None,
                'Must reference at least one encounter to create an Individual',
            )

        response = current_app.edm.request_passthrough(
            'individual.data', 'post', {'data': request_in}, ''
        )

        response_data = None
        result_data = None

        try:
            response_data = response.json()
        except Exception:
            pass
        if response.ok and response_data is not None:
            result_data = response_data.get('result', None)

        if (
            not response.ok
            or not response_data.get('success', False)
            or result_data is None
        ):
            log.warning('Individual.post failed')
            passed_message = {'message': {'key': 'error'}}
            if response_data is not None and 'message' in response_data:
                passed_message = response_data['message']
            abort(success=False, passed_message=passed_message, message='Error', code=400)

        if 'encounters' in request_in and 'encounters' not in result_data:
            # Shouldn't ever be encounters in the request_in but not result_data (!?)
            _cleanup_post_and_abort(
                result_data['id'],
                None,
                'Individual.post: request_in had an encounters list, but result_data did not.',
            )

        if not len(request_in['encounters']) == len(result_data['encounters']):
            _cleanup_post_and_abort(
                result_data['id'],
                None,
                'Individual.post: Imbalance in encounters between request_in and result_data',
            )

        # will we ever want to create an Individual with encounters that have not been created elsewhere? probably not?
        encounters = []
        for encounter_guid in request_in['encounters']:
            encounter_to_add = Encounter.query.get(encounter_guid)
            if encounter_to_add is not None:
                encounters.append(encounter_to_add)
            else:
                log.error(
                    'Individual.post: at least one encounter found in request_in or result_data was not found in the Houston database. Aborting Individual creation.'
                )
                abort(success=False, message='Error', code=500)

        # finally make the Individual if all encounters are found
        individual = Individual(
            guid=result_data['id'],
            encounters=encounters,
            version=result_data.get('version'),
        )

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
    @api.response(schemas.DetailedIndividualSchema())
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

        response = current_app.edm.get_dict('individual.data_complete', individual.guid)
        if not isinstance(response, dict):
            return response

        if len(individual.encounters) > 0:
            from app.modules.encounters.schemas import DetailedEncounterSchema

            sch = DetailedEncounterSchema(
                many=False, only=('guid', 'owner_guid', 'public')
            )
            response['result']['encounters'] = []

            for encounter in individual.encounters:
                result = sch.dump(encounter)
                response['result']['encounters'].append(result)

        return response['result']

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
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Individual details.'
        )
        with context:
            parameters.PatchIndividualDetailsParameters.perform_patch(
                args, obj=individual
            )
            db.session.merge(individual)
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
        response = individual.delete_from_edm(current_app)
        response_data = None
        if response.ok:
            response_data = response.json()
            individual.delete()

        if not response.ok or not response_data.get('success', False):
            log.warning(
                'Individual.delete %r failed: %r' % (individual.guid, response_data)
            )
            abort(
                success=False, passed_message='Delete failed', message='Error', code=400
            )

        return None
