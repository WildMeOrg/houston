# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Individuals resources
--------------------------
"""

import logging
import json
from flask_restx_patched import Resource
from flask_restx._http import HTTPStatus
from flask import request, current_app, send_file
from app.extensions import db
from app.extensions.api import Namespace, abort
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException

from . import parameters, schemas
from .models import Individual
import app.extensions.logging as AuditLog

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('individuals', description='Individuals')  # pylint: disable=invalid-name


def current_user_has_merge_request_access(individuals):
    return True  # TESTING ONLY FIXME
    if not isinstance(individuals, list) or len(individuals) < 2:
        return False
    for indiv in individuals:
        for enc in indiv.encounters:
            if enc.current_user_has_edit_permission():
                # just needs edit on a single encounter
                return True
    return False


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

        if not isinstance(rtn_json, dict) or not rtn_json.get('success', False):
            return rtn_json

        schema = DetailedIndividualSchema()
        result_json = rtn_json['result']
        result_json.update(schema.dump(individual).data)

        augmented_json = individual.augment_edm_json(result_json)

        return augmented_json

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
        response_data = None
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


@api.route('/<uuid:individual_guid>/merge')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Individual not found.',
)
@api.resolve_object_by_model(Individual, 'individual')
class IndividualByIDMerge(Resource):
    """
    Merge from a list other Individual(s)
    """

    # permission on target individual is not needed, as user may only have access to other from_individuals
    # @api.permission_required(
    #     permissions.ObjectAccessPermission,
    #     kwargs_on_request=lambda kwargs: {
    #         'obj': kwargs['individual'],
    #         'action': AccessOperation.READ,  # only requiring READ here as non-writers basically "request" a merge
    #     },
    # )
    def post(self, individual):
        from flask_login import current_user

        if not current_user or current_user.is_anonymous:
            abort(code=401)  # anonymous cannot even request a merge

        req = json.loads(request.data)
        from_individual_ids = req  # assume passed just list, check for otherwise
        if isinstance(req, dict):
            from_individual_ids = req.get('fromIndividualIds', None)
        if not isinstance(from_individual_ids, list):
            abort(
                success=False,
                message='must pass a list of individuals IDs to merge from',
                code=500,
            )
        if len(from_individual_ids) < 1:
            abort(
                success=False,
                message='list of individuals IDs to merge from cannot be empty',
                code=500,
            )

        # NOTE when merge conflict (DEX-514) is addressed, more potential args will be passed in

        meets_minimum = False
        # for which user does not have edit permissions
        blocking_encounters = []
        from_individuals = []
        for from_id in from_individual_ids:
            from_indiv = Individual.query.get(from_id)
            if not from_indiv:
                abort(
                    success=False,
                    message=f'passed from individual id={from_id} is invalid',
                    code=500,
                )
            blocking = from_indiv.get_blocking_encounters()
            if len(blocking) < len(from_indiv.encounters):
                # means user has edit permission on *at least one* encounter
                meets_minimum = True
            blocking_encounters.extend(blocking)
            from_individuals.append(from_indiv)
        # now do same for target (passed) individual
        blocking = individual.get_blocking_encounters()
        if len(blocking) < len(individual.encounters):
            meets_minimum = True
        blocking_encounters.extend(blocking)

        if not meets_minimum:
            AuditLog.frontend_fault(
                log,
                f'requested unauthorized merge from {from_individuals}',
                individual,
            )
            abort(code=403)

        # all is in order for merge; is it immediate or just a request?
        log.info(
            f'merge wants {individual} from {from_individuals} (blocking: {blocking_encounters})'
        )

        if len(blocking_encounters) > 0:
            block_ids = [str(enc.guid) for enc in blocking_encounters]
            merge_request = None
            try:
                merge_request = individual.merge_request_from(from_individuals)
            except Exception as ex:
                abort(
                    blocking_encounters=block_ids,
                    merge_request=True,
                    message=str(ex),
                    code=500,
                )
            if not merge_request:
                abort(
                    blocking_encounters=block_ids,
                    merge_request=True,
                    message='Merge failed',
                    code=500,
                )
            return {
                'blocking_encounters': block_ids,
                'request_id': merge_request['id'],
                'deadline': merge_request['deadline'].isoformat() + 'Z',
                'merge_request': True,
            }

        merge = None
        try:
            merge = individual.merge_from(*from_individuals)
        except ValueError as ex:
            abort(
                message=str(ex),
                code=500,
            )
        if not merge:
            abort(
                message='Merge failed',
                code=500,
            )
        return merge


@api.route('/<uuid:individual_guid>/featured_image', doc=False)
@api.login_required(oauth_scopes=['individuals:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Individual not found.',
)
@api.resolve_object_by_model(Individual, 'individual')
class IndividualImageByID(Resource):
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['individual'],
            'action': AccessOperation.READ,
        },
    )
    def get(self, individual):
        from io import StringIO

        asset_guid = individual.get_featured_asset_guid()
        if not asset_guid:
            return send_file(StringIO(), attachment_filename='individual_image.jpg')
        else:
            from app.modules.assets.models import Asset

            asset = Asset.query.get(asset_guid)
            if not asset:
                return send_file(StringIO(), attachment_filename='individual_image.jpg')
            try:
                image_path = asset.get_or_make_master_format_path()
            except HoustonException as ex:
                abort(ex.status_code, ex.message)
            return send_file(image_path, attachment_filename='individual_image.jpg')


# TESTING ONLY
@api.route('/merge_request/test')
class IndividualMergeRequestCreate(Resource):
    def get(self):
        individual = Individual()
        findiv = Individual()
        with db.session.begin():
            db.session.add(individual)
            db.session.add(findiv)
        params = {'deadline_delta_seconds': 60}  # speed it up
        res = individual.merge_request_from([findiv], params)
        log.warning(f'TEST CREATE {individual}, {res}')
        return {'id': res['async'].id, 'job': str(res), 'individual': str(individual)}


@api.route('/merge_request/<uuid:task_id>', defaults={'vote': None}, doc=False)
@api.route('/merge_request/<uuid:task_id>/<string:vote>')
class IndividualMergeRequestByTaskId(Resource):
    """
    Details of merge request, or register a vote on it
    """

    def get(self, task_id, vote):
        from flask_login import current_user
        import datetime

        if not current_user or current_user.is_anonymous:
            abort(code=HTTPStatus.UNAUTHORIZED)

        task_data = Individual.get_merge_request_data(str(task_id))
        if not task_data:
            abort(code=HTTPStatus.NOT_FOUND)

        if (
            'request' not in task_data
            or 'args' not in task_data['request']
            or len(task_data['request']['args']) != 3
        ):
            abort(code=HTTPStatus.INTERNAL_SERVER_ERROR, description='Invalid task data')
        all_individuals = Individual.validate_merge_request(
            task_data['request']['args'][0],
            task_data['request']['args'][1],
            task_data['request']['args'][2],
        )
        if not all_individuals:
            log.debug(f"merge request validation failed: {task_data['request']['args']}")
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                description='Merge request content not valid',
            )
        if not current_user_has_merge_request_access(all_individuals):
            abort(code=HTTPStatus.FORBIDDEN)

        # if we get here, we have access to this merge request
        if not vote:
            task_data['_individuals'] = str(all_individuals)
            deadline = datetime.datetime.fromisoformat(task_data['eta'])
            diff = deadline - datetime.datetime.now().astimezone(deadline.tzinfo)
            task_data['_secondsToDeadline'] = diff.total_seconds()
            task_data['_serverTime'] = (
                datetime.datetime.now().astimezone(deadline.tzinfo).isoformat()
            )
            task_data[
                '_deadlinePolicyDays'
            ] = Individual.get_merge_request_deadline_days()
            return task_data

        if vote not in ('allow', 'block'):
            AuditLog.backend_fault(
                log,
                f'invalid vote={vote} for merge_request id={task_id}',
                all_individuals[0],
            )
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                description=f'invalid vote value "{vote}", must be "allow" or "block"',
            )
        if vote == 'allow':
            # no real action, but lets just log it
            AuditLog.audit_log_object(
                log,
                all_individuals[0],
                f'ALLOW vote for merge_request id={task_id}',
            )
            return {'vote': vote}

        # a block vote kills the celery task so merge will not happen
        AuditLog.audit_log_object(
            log,
            all_individuals[0],
            f'BLOCK vote for merge_request id={task_id} (celery task revoked)',
        )
        current_app.celery.control.revoke(task_id)
        return {'vote': vote}
