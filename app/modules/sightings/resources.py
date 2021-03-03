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


def _cleanup_post_and_abort(
    sighting_guid, submission, message='Unknown error', log_message=None
):
    # TODO actually clean up edm based on guid!!!
    if sighting_guid is not None:
        log.warning(
            '#### TODO ####   need to properly cleanup edm sighting id=%r' % sighting_guid
        )
    if submission is not None:
        log.warning(
            '#### TODO ####   need to properly cleanup submission %r' % submission
        )
    if log_message is None:
        log_message = message
    log.error('Bailing on sighting creation: %r' % log_message)
    abort(success=False, passed_message=message, message='Error', code=400)


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
            _cleanup_post_and_abort(
                None,
                None,
                'Must have at least one encounter',
                'Sighting.post empty encounters in %r' % request_in,
            )

        response = current_app.edm.request_passthrough(
            'sighting.data', 'post', {'data': request_in}, ''
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
            log.warning('Sighting.post failed')
            passed_message = {'message': {'key': 'error'}}
            if response_data is not None and 'message' in response_data:
                passed_message = response_data['message']
            abort(success=False, passed_message=passed_message, message='Error', code=400)

        # if we get here, edm has made the sighting.  now we have to consider encounters contained within,
        # and make houston for the sighting + encounters

        # encounters via request_in and edm (result_data) need to have same count!
        if ('encounters' in request_in and 'encounters' not in result_data) or (
            'encounters' not in request_in and 'encounters' in result_data
        ):
            _cleanup_post_and_abort(
                result_data['id'],
                None,
                'Missing encounters between request_in and result',
                'Sighting.post missing encounters in one of %r or %r'
                % (request_in, result_data),
            )
        if not len(request_in['encounters']) == len(result_data['encounters']):
            _cleanup_post_and_abort(
                result_data['id'],
                None,
                'Imbalance in encounters between data and result',
                'Sighting.post imbalanced encounters in %r or %r'
                % (request_in, result_data),
            )

        try:
            all_arefs, paths_wanted = _validate_asset_references(request_in['encounters'])
        except Exception as ex:
            _cleanup_post_and_abort(
                result_data['id'],
                None,
                'Invalid assetReference data in encounter(s)',
                '_validate_asset_references threw %r on encounters=%r'
                % (ex, request_in['encounters']),
            )
        log.debug(
            '_validate_asset_references returned: %r, %r' % (all_arefs, paths_wanted)
        )

        submission = None
        assets_added = None
        pub = True
        owner_guid = None
        if current_user is not None and not current_user.is_anonymous:
            owner_guid = current_user.guid
            pub = False

        if all_arefs is not None and paths_wanted is not None:
            # files seem to exist in uploads dir, so lets make
            transaction_id = next(
                iter(all_arefs)
            )  # here is where we make single-transaciton-id assumption
            from app.modules.submissions.models import Submission

            try:
                submission = Submission.create_submission_from_tus(
                    'Sighting.post ' + result_data['id'],
                    current_user,
                    transaction_id,
                    paths=all_arefs[transaction_id],
                )
            except Exception as ex:
                _cleanup_post_and_abort(
                    result_data['id'],
                    submission,
                    'Problem with encounter/assets',
                    '%r on create_submission_from_tus transaction_id=%r paths=%r'
                    % (ex, transaction_id, all_arefs[transaction_id]),
                )

            assets_added = submission.assets
            log.debug(
                'create_submission_from_tus returned: %r => %r'
                % (submission, assets_added)
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
                        owner_guid=owner_guid,
                        public=pub,
                    )
                    enc_assets = None
                    if paths_wanted is not None:
                        # will throw exception if we dont have all we need
                        enc_assets = _enc_assets(assets_added, paths_wanted[i])
                        if enc_assets is not None:
                            encounter.add_assets_no_context(enc_assets)
                    log.debug('%r is adding enc_assets=%r' % (encounter, enc_assets))
                    sighting.add_encounter(encounter)
                    i += 1
                except Exception as ex:
                    _cleanup_post_and_abort(
                        result_data['id'],
                        submission,
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
    @api.response(schemas.DetailedSightingSchema())
    def get(self, sighting):
        """
        Get Sighting details by ID.
        """
        return sighting

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
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to delete the Sighting.'
        )
        with context:
            db.session.delete(sighting)
        return None
