# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Individuals resources
--------------------------
"""

import json
import logging
from http import HTTPStatus

from flask import request, send_file
from flask_login import current_user  # NOQA

import app.extensions.logging as AuditLog
from app.extensions import db
from app.extensions.api import Namespace, abort
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException
from flask_restx_patched import Resource

from . import parameters, schemas
from .models import Individual, IndividualMergeRequestVote

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
    @api.response(schemas.DetailedIndividualSchema())
    def post(self, args):
        """
        Create a new instance of Individual.
        """
        import app.modules.utils as util
        from app.extensions.elapsed_time import ElapsedTime
        from app.modules.site_settings.helpers import SiteSettingCustomFields
        from app.modules.site_settings.models import Taxonomy

        timer = ElapsedTime()

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
            abort(400, 'No Encounters in POST')

        from app.modules.encounters.models import Encounter

        encounters = []

        for enc_json in request_in['encounters']:
            if enc_json['id'] is not None:
                encounter = Encounter.query.get(enc_json['id'])
                if encounter is not None and encounter.individual_guid is not None:
                    abort(
                        400,
                        'Individual POST included an encounter that already has an Individual.',
                    )
                encounters.append(encounter)

        names = self._parse_names(request_in.get('names'))

        error_messages = []
        in_sex = request_in.get('sex')
        if not util.is_valid_sex(in_sex):  # None passes True here
            error_messages.append(f'"{in_sex}" not a valid value for sex')
        in_tob = request_in.get('timeOfBirth')
        if in_tob and not util.is_valid_datetime_string(in_tob):
            error_messages.append(f'"{in_tob}" not a valid value for timeOfBirth')
        in_tod = request_in.get('timeOfDeath')
        if in_tod and not util.is_valid_datetime_string(in_tod):
            error_messages.append(f'"{in_tod}" not a valid value for timeOfDeath')
        in_tx = request_in.get('taxonomy')
        if not in_tx:
            error_messages.append('a taxonomy guid is required')
        else:
            try:
                Taxonomy(in_tx)
            except ValueError:
                error_messages.append(f'"{in_tx}" not a valid taxonomy guid')
        in_cf = request_in.get('customFields')
        if in_cf:
            if not isinstance(in_cf, dict):
                error_messages.append(f'{in_cf}: customFields must be a dict')
            else:
                for cfd_id in in_cf:
                    if not SiteSettingCustomFields.is_valid_value_for_class(
                        'Individual', cfd_id, in_cf[cfd_id]
                    ):
                        error_messages.append(
                            f'customFields id={cfd_id} value="{in_cf[cfd_id]}" is not valid'
                        )
        if error_messages:  # something failed
            msg = f"problem with passed values: {'; '.join(error_messages)}"
            log.error(f'Individual.post: {msg}. Aborting Individual creation.')
            abort(400, msg)

        # finally make the Individual if all encounters are found
        individual = Individual(
            encounters=encounters,
            names=names,
            comments=request_in.get('comments'),
            sex=in_sex,
            time_of_birth=in_tob,
            time_of_death=in_tod,
            taxonomy_guid=in_tx,
            custom_fields=in_cf,
        )
        individual.update_autogen_names(current_user)
        AuditLog.user_create_object(log, individual, duration=timer.elapsed())
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Individual'
        )

        with context:
            db.session.add(individual)
        db.session.refresh(individual)

        return individual

    def _parse_names(self, names_data):
        names = []
        if not names_data or not isinstance(names_data, list):
            return names

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
                        abort(
                            400,
                            f'Invalid user guid ({user_guid}) in name data {name_json}',
                        )

                    preferring_users.append(user)
            name_context = name_json.get('context')
            name_value = name_json.get('value')
            if not name_context or not name_value:
                AuditLog.frontend_fault(log, f'invalid name data {name_json}')
                abort(400, f'Invalid name data {name_json}')
            if Name.is_reserved_context(name_context):
                AuditLog.frontend_fault(log, f'reserved context in {name_json}')
                abort(400, f'Reserved context value in {name_json}')
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
    @api.response(schemas.ElasticsearchIndividualReturnSchema(many=True))
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
    @api.response(schemas.ElasticsearchIndividualReturnSchema(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()

        args['total'] = True
        return Individual.elasticsearch(search, **args)


@api.route('/remove_all_empty')
@api.login_required(oauth_scopes=['individuals:write'])
class IndividualRemoveEmpty(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Individual,
            'action': AccessOperation.DELETE,
        },
    )
    def post(self):
        try:
            Individual.remove_all_empty()
        except HoustonException as ex:
            abort(400, ex.message)


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
        return individual

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

        context = api.commit_or_abort(
            db.session,
            default_error_message='Failed to update Individual details.',
        )

        with context:
            try:
                parameters.PatchIndividualDetailsParameters.perform_patch(
                    args, individual
                )
            except HoustonException as ex:
                # Only 409 and 422 are valid for patch (so Jon says)
                status_code = ex.status_code if ex.status_code == 422 else 409
                abort(status_code, ex.message)

        # via cdx-7, we force user to set taxonomy during any patch they do
        if not individual.taxonomy_guid:
            abort(409, 'you must set taxonomy on this individual')

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

        # now that we have from_individuals and all is in order, do some checks on override
        if (
            parameters
            and 'override' in parameters
            and isinstance(parameters['override'], dict)
        ):
            tx_guid = individual.taxonomy_guid or parameters['override'].get(
                'taxonomy_guid'
            )
            if tx_guid:
                # see indiv.merge_names() for more on this override
                name_override = parameters['override'].get('name_context')
                # we basically only care about checking autogen ones (for taxonomy validity)
                if name_override and isinstance(name_override, dict):
                    from app.modules.autogenerated_names.models import (
                        AUTOGEN_NAME_CONTEXT_PREFIX,
                        AutogeneratedName,
                        AutogeneratedNameType,
                    )

                    for ctx in name_override.keys():
                        if not ctx.startswith(AUTOGEN_NAME_CONTEXT_PREFIX):
                            continue
                        agn = AutogeneratedName.query.get(
                            ctx[len(AUTOGEN_NAME_CONTEXT_PREFIX) :]
                        )
                        if (
                            agn
                            and agn.type == AutogeneratedNameType.auto_species.value
                            and str(agn.reference_guid) != str(tx_guid)
                        ):
                            AuditLog.frontend_fault(
                                log,
                                f'override results in taxonomy_guid {tx_guid} and {agn}, which are incompatible',
                                individual,
                            )
                            abort(
                                code=400,
                                message='override results in incompatible AutogeneratedName and Taxonomy',
                            )
                        # TODO handle other types of AGN

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
                all_individuals, request_data, NotificationType.individual_merge_blocked
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
            [target_individual] + all_individuals,
            request_data,
            NotificationType.individual_merge_complete,
        )
        return {'vote': vote, 'merge_completed': True}


@api.route('/merge_conflict_check')
class IndividualMergeConflictCheck(Resource):
    def post(self):

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
    @api.response(schemas.DebugIndividualSchema())
    def get(self, individual):
        """
        Get Individual debug by ID.
        """
        return individual


@api.route('/validate')
class FlatfileNameValidation(Resource):
    # values passed in from flatfile are val/index pairs:
    # [
    #   ["Zebulon", 1],
    #   ["Zebulon", 2],
    #   ["Zebrandon", 3],
    #   ["Zebrelda", 300],
    #   ["Zesus", 46]
    # ]
    def post(self):
        from collections import defaultdict

        from app.modules.names.models import DEFAULT_NAME_CONTEXT, Name

        if not current_user or current_user.is_anonymous:
            abort(code=401)
        if not isinstance(request.json, list):
            abort(
                message='Must be passed a list of flatfile-formatted name-index pairs',
                code=500,
            )

        # want to preserve order here
        query_name_vals = [val_id_pair[0] for val_id_pair in request.json]
        query_indices = [val_id_pair[1] for val_id_pair in request.json]

        db_names = Name.query.filter(
            Name.value.in_(query_name_vals), Name.context == DEFAULT_NAME_CONTEXT
        )
        # maps a name value to list of individuals with that name value
        db_name_lookup = defaultdict(list)
        for name in db_names:
            db_name_lookup[name.value].append(str(name.individual_guid))

        rtn_json = []
        for name_val, index in zip(query_name_vals, query_indices):
            if not name_val or name_val.strip() == '':
                continue
            elif name_val in db_name_lookup and len(db_name_lookup[name_val]) == 1:
                name_info = {
                    'message': f'Corresponds to existing individual {db_name_lookup[name_val][0]}.',
                    'level': 'info',
                }
            elif name_val in db_name_lookup and len(db_name_lookup[name_val]) > 1:
                name_info = {
                    'message': f'ERROR: cannot resolve this name to a unique individual. Individuals sharing this name are {db_name_lookup[name_val]}.',
                    'level': 'error',
                }
            else:
                name_info = {
                    'message': 'ERROR: cannot resolve this name to an existing individual. New name creation is not yet supported in bulk upload.',
                    'level': 'error',
                }
            name_json = {'value': name_val, 'info': [name_info]}
            rtn_json.append([name_json, index])

        return rtn_json
