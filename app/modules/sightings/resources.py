# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Sightings resources
--------------------------
"""

import logging

from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus
from flask_login import current_user  # NOQA
from flask import request, current_app

from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation


from . import parameters, schemas
from .models import Sighting

from app.extensions.api import abort
import json
import os

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('sightings', description='Sightings')  # pylint: disable=invalid-name


class SightingCleanup(object):
    def __init__(self):
        self.sighting_guid = None
        self.submission = None

    def rollback_and_abort(self, message='Unknown error', log_message=None, error_code=400):
        if log_message is None:
            log_message = message
        log.error('Bailing on sighting creation: %r' % log_message)
        if self.sighting_guid is not None:
            log.warning('Cleanup removing Sighting %r from EDM' % self.sighting_guid)
            Sighting.delete_from_edm_by_guid(current_app, self.sighting_guid)
        if self.submission is not None:
            log.warning('Cleanup removing %r' % self.submission)
            self.submission.delete()
            self.submission = None
        abort(success=False, passed_message=message, message='Error', code=error_code)


def _validate_asset_references(enc_list):
    # now we handle asset-related json that came in. note: arrays should be parallel in request_in/result_data
    # we make sure assetReferences is well-formed and also maps (future) assets to encounters

    # NOTE for simplicity i am going to assume assetReferences *share a common transaction id*  !!
    #  this will very likely always be true, but in the event it proves not to be, this will have to be altered
    #  to do multiple create_submission_from_tus() calls

    all_arefs = {}  # all paths needed, keyed by transaction id
    paths_wanted = (
        []
    )  # parallel list (to encounters) of set of asset paths for that encounter
    i = 0
    while i < len(enc_list):
        enc_data = enc_list[i]
        paths_wanted.append(set())
        # TODO handle regular .assets flavor
        # TODO genericize this across here and encounters
        if 'assetReferences' not in enc_data or not isinstance(
            enc_data['assetReferences'], list
        ):
            i += 1
            continue  # dont have any assetReferences!  try next encounter....

        for aref in enc_data['assetReferences']:
            if (
                not isinstance(aref, dict)
                or 'path' not in aref
                or 'transactionId' not in aref
            ):
                log.error('Sighting.post malformed assetReferences data: %r' % (aref))
                raise ValueError('malformed assetReference in json')
            paths_wanted[i].add(aref['path'])
            if aref['transactionId'] not in all_arefs:
                all_arefs[aref['transactionId']] = set()
            all_arefs[aref['transactionId']].add(aref['path'])

        i += 1  # on to next encounter...

    if len(all_arefs.keys()) < 1:  # hmm... no one had any assetReferences!
        return None, None

    # now we make sure we have the files we need so we can abort if not (they may fail later for other reasons)
    from app.extensions.tus import tus_upload_dir

    for tid in all_arefs:
        for path in all_arefs[tid]:
            file_path = os.path.join(
                tus_upload_dir(current_app, transaction_id=tid), path
            )
            try:
                sz = os.path.getsize(file_path)  # 2for1
            except OSError as err:
                log.error(
                    'Sighting.post OSError %r assetReferences data: %r / %r'
                    % (err, tid, path)
                )
                raise ValueError('Error with path ' + path)
            if sz < 1:
                log.error(
                    'Sighting.post zero-size file for assetReferences data: %r / %r'
                    % (tid, path)
                )
                raise ValueError('Error with path ' + path)

    return all_arefs, paths_wanted


def _enc_assets(assets, paths_wanted):
    if len(paths_wanted) < 1:
        return None
    matches = []
    for asset in assets:
        # log.info('match for %r x %r' % (asset, paths_wanted))
        if asset.path in paths_wanted:
            matches.append(asset)
    assert len(matches) == len(paths_wanted), (
        'not all assets wanted found for %r' % paths_wanted
    )
    return matches


@api.route('/')
class Sightings(Resource):
    """
    Manipulations with Sightings.
    """

    @api.login_required(oauth_scopes=['sightings:read'])
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Sighting,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseSightingSchema(many=True))
    def get(self, args):
        """
        List of Sighting.

        Returns a list of Sighting starting from ``offset`` limited by ``limit``
        parameter.
        """
        return Sighting.query.offset(args['offset']).limit(args['limit'])

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Sighting,
            'action': AccessOperation.WRITE,
        },
    )
    @api.parameters(parameters.CreateSightingParameters())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Sighting.
        """

        cleanup = SightingCleanup()
        request_in = {}
        try:
            request_in_ = json.loads(request.data)
            request_in.update(request_in_)
        except Exception:
            pass

        # i think this was official declared as law today 2021-02-24
        if (
            'encounters' not in request_in
            or not isinstance(request_in['encounters'], list)
            or len(request_in['encounters']) < 1
        ):
            cleanup.rollback_and_abort(
                'Must have at least one encounter',
                'Sighting.post empty encounters in %r' % request_in,
            )

        # we must resolve any weirdness with owner/submitter ahead of time so we can bail if problems
        pub = False
        owner = None
        submitter_guid = None
        if current_user is None or current_user.is_anonymous:
            from app.modules.users.models import User
            owner = User.get_public_user()
            pub = True
            submitter_email = request_in.get('submitterEmail', None)
            log.info(f'Anonymous submission posted, submitter_email={submitter_email}')
            if submitter_email is not None:  # if not provided, submitter_guid is allowed to be null
                exists = User.find(email=submitter_email)
                if exists is None:
                    new_inactive = User.ensure_user(submitter_email, User.initial_random_password(), is_active=False)
                    submitter_guid = new_inactive.guid
                    log.info(f'New inactive user created as submitter: {new_inactive}')
                elif not exists.is_active:  # we trust it, what can i say?  they are inactive so its weak and public anyway
                    submitter_guid = exists.guid
                    log.info(f'Existing inactive user assigned to submitter: {exists}')
                else:  # now this is no good; this *active* user must login!  no spoofing active users.
                    cleanup.rollback_and_abort(
                        'Invalid submitter data',
                        f'Anonymous submitter using active user email {submitter_email}; rejecting',
                        error_code=403
                    )
        else:  # logged-in user
            owner = current_user
            submitter_guid = current_user.guid

        response = current_app.edm.request_passthrough(
            'sighting.data', 'post', {'data': request_in}, ''
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
            passed_message = {'message': {'key': 'error'}}
            if response_data is not None and 'message' in response_data:
                passed_message = response_data['message']
            cleanup.rollback_and_abort(passed_message, 'Sighting.post failed')

        # Created it, need to clean it up if we rollback
        cleanup.sighting_guid = result_data['id']

        # if we get here, edm has made the sighting.  now we have to consider encounters contained within,
        # and make houston for the sighting + encounters

        # encounters via request_in and edm (result_data) need to have same count!
        if ('encounters' in request_in and 'encounters' not in result_data) or (
            'encounters' not in request_in and 'encounters' in result_data
        ):
            cleanup.rollback_and_abort(
                'Missing encounters between request_in and result',
                'Sighting.post missing encounters in one of %r or %r'
                % (request_in, result_data),
            )
        if not len(request_in['encounters']) == len(result_data['encounters']):
            cleanup.rollback_and_abort(
                'Imbalance in encounters between data and result',
                'Sighting.post imbalanced encounters in %r or %r'
                % (request_in, result_data),
            )

        try:
            all_arefs, paths_wanted = _validate_asset_references(request_in['encounters'])
        except Exception as ex:
            cleanup.rollback_and_abort(
                'Invalid assetReference data in encounter(s)',
                '_validate_asset_references threw %r on encounters=%r'
                % (ex, request_in['encounters']),
            )
        log.debug(
            '_validate_asset_references returned: %r, %r' % (all_arefs, paths_wanted)
        )

        submission = None

        if all_arefs is not None and paths_wanted is not None:
            # files seem to exist in uploads dir, so lets make
            transaction_id = next(
                iter(all_arefs)
            )  # here is where we make single-transaciton-id assumption
            from app.modules.submissions.models import Submission

            try:
                submission = Submission.create_submission_from_tus(
                    'Sighting.post ' + result_data['id'],
                    owner,
                    transaction_id,
                    paths=all_arefs[transaction_id],
                )
            except Exception as ex:
                cleanup.submission = submission
                cleanup.rollback_and_abort(
                    'Problem with encounter/assets',
                    '%r on create_submission_from_tus transaction_id=%r paths=%r'
                    % (ex, transaction_id, all_arefs[transaction_id]),
                )
            cleanup.submission = submission

            log.debug(
                'create_submission_from_tus returned: %r => %r'
                % (submission, submission.assets)
            )

        sighting = Sighting(
            guid=result_data['id'],
            version=result_data.get('version', 2),
        )

        # create encounters (including adding their assets if applicable)
        from app.modules.encounters.models import Encounter

        if isinstance(result_data['encounters'], list):
            i = 0
            while i < len(result_data['encounters']):
                try:
                    encounter = Encounter(
                        guid=result_data['encounters'][i]['id'],
                        version=result_data['encounters'][i].get('version', 2),
                        owner_guid=owner.guid,
                        submitter_guid=submitter_guid,
                        public=pub,
                    )
                    enc_assets = None
                    if paths_wanted is not None:
                        # will throw exception if we dont have all we need
                        enc_assets = _enc_assets(submission.assets, paths_wanted[i])
                        if enc_assets is not None:
                            encounter.add_assets_no_context(enc_assets)
                    log.debug('%r is adding enc_assets=%r' % (encounter, enc_assets))
                    sighting.add_encounter(encounter)
                    i += 1
                except Exception as ex:
                    cleanup.rollback_and_abort(
                        'Problem with encounter/assets',
                        '%r on encounter %d: paths_wanted=%r; enc=%r'
                        % (ex, i, paths_wanted, request_in['encounters'][i]),
                    )

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to persist new houston Sighting'
        )
        with context:
            db.session.add(sighting)
        rtn = {
            'success': True,
            'result': {
                'id': str(sighting.guid),
                'version': sighting.version,
                'encounters': result_data['encounters'],
            },
        }
        return rtn


@api.route('/<uuid:sighting_guid>')
@api.login_required(oauth_scopes=['sightings:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Sighting not found.',
)
@api.resolve_object_by_model(Sighting, 'sighting')
class SightingByID(Resource):
    """
    Manipulations with a specific Sighting.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.READ,
        },
    )
    def get(self, sighting):
        """
        Get Sighting details by ID.
        """

        # note: should probably _still_ check edm for: stale cache, deletion!
        #      user.edm_sync(version)

        response = current_app.edm.get_dict('sighting.data_complete', sighting.guid)
        if not isinstance(response, dict):  # some non-200 thing, incl 404
            return response

        return sighting.augment_edm_json(response['result'])

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['sightings:write'])
    @api.parameters(parameters.PatchSightingDetailsParameters())
    @api.response(schemas.DetailedSightingSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, sighting):
        """
        Patch Sighting details by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Sighting details.'
        )
        with context:
            parameters.PatchSightingDetailsParameters.perform_patch(args, obj=sighting)
            db.session.merge(sighting)
        return sighting

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['sighting'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['sightings:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, sighting):
        """
        Delete a Sighting by ID.
        """
        # first try delete on edm
        response = sighting.delete_from_edm(current_app)
        response_data = None
        if response.ok:
            response_data = response.json()

        if not response.ok or not response_data.get('success', False):
            log.warning('Sighting.delete %r failed: %r' % (sighting.guid, response_data))
            abort(
                success=False, passed_message='Delete failed', message='Error', code=400
            )

        # if we get here, edm has deleted the sighting, now houston feather
        # TODO handle failure of feather deletion (when edm successful!)  out-of-sync == bad
        sighting.delete_cascade()
        return None
