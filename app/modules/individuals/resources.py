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
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException

from . import parameters, schemas
from .models import Individual, IndividualMergeRequestVote
import app.extensions.logging as AuditLog

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('individuals', description='Individuals')  # pylint: disable=invalid-name


def current_user_has_merge_request_access(individuals):
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
            # we try deleting from edm *regardless of failed_individual*, as sometimes
            #   the houston individual did not get made, but the edm did
            log.error(f'Attempting to delete Individual {self.individual_guid} from EDM')
            try:
                current_app.edm.request_passthrough(
                    'individual.data', 'delete', {}, self.individual_guid
                )
            except Exception:
                pass
            if failed_individual is not None:
                with db.session.begin():
                    db.session.delete(failed_individual)
                log.error(
                    'The Individual with guid %r has been deleted from Houston'
                    % self.individual_guid
                )
        abort(code, message)


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
    @api.response(schemas.DetailedIndividualSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Individual.
        """
        return Individual.query_search(args=args)

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
                missing_encounter = result_encounter_json['id']
                log.error(
                    f'Individual.post: at least one encounter found in request_in or result_data was not found'
                    f' in the Houston database {missing_encounter}.  Aborting Individual creation.'
                )
                cleanup.rollback_and_abort(
                    message='Encounter(s) in request or response not in Houston db.',
                    code=500,
                )

        names = self._parse_names(request_in.get('names'), cleanup)

        # finally make the Individual if all encounters are found
        individual = Individual(
            guid=result_data['id'],
            encounters=encounters,
            names=names,
            version=result_data.get('version'),
        )
        AuditLog.user_create_object(log, individual, duration=timer.elapsed())
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Individual'
        )

        with context:
            db.session.add(individual)
        db.session.refresh(individual)

        return individual.get_detailed_json()

    def _parse_names(self, names_data, cleanup):
        names = []
        if not names_data or not isinstance(names_data, list):
            return names
        from flask_login import current_user
        from app.modules.names.models import Name

        for name_json in names_data:
            preferring_users = []
            if 'preferring_users' in name_json and isinstance(
                name_json['preferring_users'], list
            ):
                from app.modules.users.models import User

                for user_guid in name_json['preferring_users']:
                    user = User.query.get(user_guid)
                    if not user:
                        AuditLog.frontend_fault(
                            log,
                            f'invalid user guid ({user_guid}) in preferring_users {name_json}',
                        )
                        cleanup.rollback_and_abort(
                            message=f'Invalid user guid ({user_guid}) in name data {name_json}',
                            code=400,
                        )
                    preferring_users.append(user)
            name_context = name_json.get('context')
            name_value = name_json.get('value')
            if not name_context or not name_value:
                AuditLog.frontend_fault(log, f'invalid name data {name_json}')
                cleanup.rollback_and_abort(
                    message=f'Invalid name data {name_json}',
                    code=400,
                )
            new_name = Name(
                context=name_context,
                value=name_value,
                creator_guid=current_user.guid,
            )
            # new_name.add_preferring_users(preferring_users)
            names.append(new_name)
        return names


@api.route('/search')
@api.login_required(oauth_scopes=['individuals:read'])
class IndividualElasticsearch(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Individual,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedIndividualSchema(many=True))
    @api.paginate()
    def get(self, args):
        search = {}
        args['total'] = True
        return Individual.elasticsearch(search, **args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Individual,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedIndividualSchema(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()

        args['total'] = True
        return Individual.elasticsearch(search, **args)


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
            return {}

        return individual.get_detailed_json()

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

        edm_args = [
            arg
            for arg in args
            if arg['path'] in parameters.PatchIndividualDetailsParameters.PATH_CHOICES_EDM
        ]

        if len(edm_args) > 0:
            log.debug(f'wanting to do edm patch on args={edm_args}')
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
                if isinstance(ex.message, dict):
                    message = ex.message.get('details', ex.message)
                else:
                    message = ex.message
                abort(ex.status_code, message)

            # TODO handle individual deletion if last encounter removed
            # changed something on EDM, remove the cache
            individual.remove_cached_edm_data()

        if houston_args:
            if not edm_args:
                # regular houston-patching
                context = api.commit_or_abort(
                    db.session,
                    default_error_message='Failed to update Individual details.',
                )
            else:
                # irregular houston-patching, where we need to report that EDM data was set if houston setting failed
                context = api.commit_or_abort(
                    db.session,
                    default_error_message='Failed to update Individual details.',
                    code=417,  # Arbitrary choice (Expectation Failed)
                    fields_written=edm_args,
                )
            with context:
                try:
                    parameters.PatchIndividualDetailsParameters.perform_patch(
                        houston_args, individual
                    )
                except HoustonException as ex:
                    abort(ex.status_code, ex.message)

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

        response_data = response.json()
        if not response.ok or not response_data.get('success', False):
            log.warning(
                'Individual.delete:  Failed to delete id %r using delete_from_edm(). response_data=%r'
                % (individual.guid, response_data)
            )
        try:
            individual.delete()
        except Exception:
            abort(400, 'Delete failed')
        AuditLog.delete_object(log, individual)
        return None


@api.route('/<uuid:individual_guid>/cooccurrence')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Individual not found.',
)
@api.resolve_object_by_model(Individual, 'individual')
@api.response(schemas.DetailedIndividualSchema(many=True))
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
        parameters = None
        if isinstance(req, dict):
            from_individual_ids = req.get('fromIndividualIds', None)
            if 'parameters' in req and isinstance(req['parameters'], dict):
                parameters = req['parameters']
        if not isinstance(from_individual_ids, list):
            abort(500, 'must pass a list of individuals IDs to merge from')
        if len(from_individual_ids) < 1:
            abort(500, 'list of individuals IDs to merge from cannot be empty')

        meets_minimum = False
        # for which user does not have edit permissions
        blocking_encounters = []
        from_individuals = []
        for from_id in from_individual_ids:
            from_indiv = Individual.query.get(from_id)
            if not from_indiv:
                abort(500, f'passed from individual id={from_id} is invalid')
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
                merge_request = individual.merge_request_from(
                    from_individuals, parameters=parameters
                )
            except Exception as ex:
                AuditLog.houston_fault(log, str(ex), individual)
                abort(
                    blocking_encounters=block_ids,
                    merge_request=True,
                    message=str(ex),
                    code=500,
                )
            if not merge_request:
                AuditLog.houston_fault(log, 'merge_request fail', individual)
                abort(
                    blocking_encounters=block_ids,
                    merge_request=True,
                    message='Merge failed',
                    code=500,
                )
            # as a stakeholder, this automatically counts as a vote for this user
            IndividualMergeRequestVote.record_vote(
                merge_request['id'], current_user, 'allow'
            )
            return {
                'blocking_encounters': block_ids,
                'request_id': merge_request['id'],
                'deadline': merge_request['deadline'].isoformat() + 'Z',
                'merge_request': True,
            }

        merge = None
        try:
            merge = individual.merge_from(*from_individuals, parameters=parameters)
        except ValueError as ex:
            AuditLog.houston_fault(log, str(ex), individual)
            abort(
                message=str(ex),
                code=500,
            )
        if not merge:
            AuditLog.houston_fault(log, 'merge fail', individual)
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


@api.route('/merge_request/<uuid:task_id>')
class IndividualMergeRequestByTaskId(Resource):
    def _validate_request(self, task_id):
        from flask_login import current_user

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
        return all_individuals, task_data

    """
    Details of merge request
    """

    def get(self, task_id):
        import datetime

        all_individuals, task_data = self._validate_request(task_id)
        task_data['_individuals'] = str(all_individuals)
        deadline = datetime.datetime.fromisoformat(task_data['eta'])
        diff = deadline - datetime.datetime.now().astimezone(deadline.tzinfo)
        task_data['_secondsToDeadline'] = diff.total_seconds()
        task_data['_serverTime'] = (
            datetime.datetime.now().astimezone(deadline.tzinfo).isoformat()
        )
        task_data['_deadlinePolicyDays'] = Individual.get_merge_request_deadline_days()
        return task_data

    """
    Vote on a merge request
    """

    def post(self, task_id):
        from flask_login import current_user
        from app.modules.notifications.models import NotificationType

        vote = request.json.get('vote')
        all_individuals, task_data = self._validate_request(task_id)
        if vote not in ('allow', 'block'):
            AuditLog.frontend_fault(
                log,
                f'invalid vote={vote} for merge_request id={task_id}',
                all_individuals[0],
            )
            abort(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                description=f'invalid vote value "{vote}", must be "allow" or "block"',
            )

        # we take a valid vote, and record it.  now we have 3 cases:
        # 1. block vote kills the task outright
        # 2. allow vote that is final one needed, which triggers merge *now* ("unanimous")
        # 3. allow vote, but not unanimous - no-op and we keep waiting (task is still valid)
        IndividualMergeRequestVote.record_vote(task_id, current_user, vote)

        if vote == 'block':
            AuditLog.audit_log_object(
                log,
                all_individuals[0],
                f'BLOCK vote for merge_request id={task_id} (celery task revoked)',
            )
            Individual.merge_request_cancel_task(task_id)
            request_data = {
                'id': task_id,
                'from_individual_ids': task_data['request']['args'][1],
                'merge_outcome': 'blocked',
            }
            Individual.merge_notify(
                all_individuals, request_data, NotificationType.individual_merge_complete
            )
            return {'vote': vote, 'merge_request_cancelled': True}

        # we only care about *number of votes* here really, cuz they all must be "allow" if we got this far
        voters = IndividualMergeRequestVote.get_voters(task_id)
        stakeholders = Individual.get_merge_request_stakeholders(all_individuals)
        needed = len(stakeholders) - len(voters)
        if needed > 0:
            AuditLog.audit_log_object(
                log,
                all_individuals[0],
                f'ALLOW vote for merge_request id={task_id} ({needed} more votes needed)',
            )
            return {'vote': vote, 'votes_needed': needed}

        # unanimous!  lets make merge happen
        AuditLog.audit_log_object(
            log,
            all_individuals[0],
            f'ALLOW vote for merge_request id={task_id}; unanimous, triggering merge',
        )
        target_individual = all_individuals.pop(0)
        try:
            res = target_individual.merge_from(*all_individuals)
        except Exception as ex:
            res = f'Exception caught: {str(ex)}'
        if not isinstance(res, dict):
            msg = f'{task_id} (via unanimous vote) merge_from failed: {res}'
            AuditLog.houston_fault(log, msg, target_individual)
            abort(500, msg)

        Individual.merge_request_cleanup(task_id)
        # notify users that merge has happened
        #   NOTE request_data here may need some altering depending on what final templates look like
        #   also unclear who *sender* will be, so that may need to be passed
        request_data = {
            'id': task_id,
            'from_individual_ids': task_data['request']['args'][1],
            'merge_outcome': 'unanimous',
        }
        Individual.merge_notify(
            [target_individual], request_data, NotificationType.individual_merge_complete
        )
        return {'vote': vote, 'merge_completed': True}


@api.route('/merge_conflict_check')
class IndividualMergeConflictCheck(Resource):
    def post(self):
        from flask_login import current_user

        if not current_user or current_user.is_anonymous:
            abort(code=401)
        if not isinstance(request.json, list):
            abort(message='must be passed a list of individual ids', code=500)
        if len(request.json) < 2:
            abort(message='must be passed at least 2 individual ids', code=500)
        individuals = []
        for indiv_id in request.json:
            indiv = Individual.query.get(indiv_id)
            if not indiv:
                abort(message=f'Individual {indiv_id} not found', code=404)
            individuals.append(indiv)
        if not current_user_has_merge_request_access(individuals):
            abort(code=403)

        conflicts = Individual.find_merge_conflicts(individuals)
        return conflicts


@api.route('/debug/<uuid:individual_guid>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Individual not found.',
)
@api.resolve_object_by_model(Individual, 'individual')
class IndividualDebugByID(Resource):
    """
    Manipulations with a specific Individual.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['individual'],
            'action': AccessOperation.READ_DEBUG,
        },
    )
    def get(self, individual):
        """
        Get Individual details by ID.
        """
        if individual is not None:
            log.info(
                f'GET passthrough called for Individual with GUID: {individual.guid}'
            )
        else:
            log.error('GET passthrough called for nonexistent Individual')
            return {}

        return individual.get_debug_json()

@api.route('/validation')
class FlatfileNameValidation(Resource):
# values passed in from flatfile are val/index pairs:
# [
#   ["Zebulon", 1],
#   ["Zebrucifer", 2],
#   ["Zebrelda", 3],
#   ["Zesus", 4]
# ]

    from app.modules.names.models import DEFAULT_NAME_CONTEXT

    def get(self):
        from flask_login import current_user

        if not current_user or current_user.is_anonymous:
            abort(code=401)
        if not isinstance(request.json, list):
            abort(message='Must be passed a list of flatfile-formatted name-index pairs', code=500)

        # keeping this dict in case they are sent in a weird order, which is allowed by flatfile
        query_index_dict = {val_id_pair[0]: val_id_pair[1] for val_id_pair in request.json}
        # want to preserve order here
        query_names = [val_id_pair[0] for val_id_pair in request.json]

        db_names = Name.query.filter(
            Name.value.in_(query_names), Name.context == DEFAULT_NAME_CONTEXT
        )
        db_name_lookup = {name.value: name.individual_guid for name in db_names}

        rtn_json = []
        for name in query_names:
            if name in db_name_lookup:
                name_resp = {
                    "message": f"Corresponds to existing individual {db_name_lookup(name)}",
                    "level": "info",
                }
            else:
                name_resp = {
                    "message": f"This is a new name and submission will create a new individual",
                    "level": "warning",
                }
            rtn_json.append([name_resp, query_index_dict[name]])

        return rtn_json

# // what should be passed back in this case
# [
#   [
#     {
#       value: "john@doe.com", // not required if not changing value
#       info: [
#         {
#           message: "Error message goes here",
#           level: "info" // should be 'info', 'warning' or 'error'
#         }
#       ]
#     },
#     1
#   ],
#   [
#     {
#       value: "steve@something.com", // not required if not changing value
#       info: [
#         {
#           message: "Error message goes here",
#           level: "info" // should be 'info', 'warning' or 'error'
#         }
#       ]
#     },
#     3
#   ]
# ]







