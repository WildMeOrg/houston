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


def _cleanup_post_and_abort(sighting_guid, submission, message='Unknown error'):
    # TODO actually clean up edm based on guid!!!
    if sighting_guid is not None:
        log.warning('TODO need to properly cleanup edm sighting id=%r' % sighting_guid)
    if submission is not None:
        log.warning('TODO need to properly cleanup submission %r' % submission)
    log.error('Bailing on sighting creation: %r' % message)
    abort(success=False, passed_message=message, message='Error', code=400)


def _enc_assets(assets, paths_wanted):
    if len(paths_wanted) < 1:
        return None
    matches = []
    for asset in assets:
        # log.info('match for %r x %r' % (asset, paths_wanted))
        if asset.path in paths_wanted:
            matches.append(asset)
    assert len(matches) == len(paths_wanted), (
        'not all assets wanted found for ' + paths_wanted
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
            log.error('Sighting.post empty encounters in %r' % (request_in,))
            _cleanup_post_and_abort(None, None, 'Must have at least one encounter')

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

        # FIXME must cleanup edm cruft!
        if ('encounters' in request_in and 'encounters' not in result_data) or (
            'encounters' not in request_in and 'encounters' in result_data
        ):
            log.error(
                'Sighting.post missing encounters in one of %r or %r'
                % (request_in, result_data)
            )
            _cleanup_post_and_abort(
                result_data['id'],
                None,
                'Missing encounters between request_in and result',
            )
        if not len(request_in['encounters']) == len(result_data['encounters']):
            log.error(
                'Sighting.post imbalanced encounters in %r or %r'
                % (request_in, result_data)
            )
            _cleanup_post_and_abort(
                result_data['id'], None, 'Imbalance in encounters between data and result'
            )

        # now we handle asset-related json that came in. note: arrays should be parallel in data/result_data
        # this makes sure assetReferences is well-formed and also maps (future) assets to encounters

        # NOTE for simplicity i am going to assume assetReferences *share a common transaction id*  !!
        #  this will very likely always be true, but in the event it proves not to be, this will have to be altered
        #  to do multiple create_submission_from_tus() calls below

        arefs_found = {}  # asset refs across all encounters (to handle duplicates)
        paths_wanted = (
            []
        )  # parallel list to encounters of list of asset paths for that encounter
        i = 0
        while i < len(request_in['encounters']):
            enc_data = request_in['encounters'][i]
            paths_wanted[i] = []
            # TODO handle regular .assets flavor
            # TODO genericize this across here and encounters
            if 'assetReferences' in enc_data and isinstance(
                enc_data['assetReferences'], list
            ):
                for aref in enc_data['assetReferences']:
                    if (
                        not isinstance(aref, dict)
                        or 'path' not in aref
                        or 'transactionId' not in aref
                    ):
                        log.error(
                            'Sighting.post malformed assetReferences data: %r' % (aref)
                        )
                        _cleanup_post_and_abort(
                            result_data['id'], None, 'Malformed assetReferences data'
                        )
                    paths_wanted[i].append(aref['path'])
                    key = ':'.join((aref['transactionId'], aref['path']))
                    if key in arefs_found:
                        arefs_found[key]['encs'].append(i)
                    else:
                        arefs_found[key] = aref.copy()
                        arefs_found[key]['encs'] = [i]
            i += 1

        # now we have a mapping of encounters to assetReferences... so we try to create the submission + assets
        #   first we make sure we have the files we need so we can abort if not (they may fail later for other reasons)
        from app.extensions.tus import tus_upload_dir

        transaction_id = None  # see note above about single common transaction id
        for key in arefs_found:
            aref = arefs_found[key]
            transaction_id = aref['transactionId']
            file_path = os.path.join(
                tus_upload_dir(current_app, transaction_id=transaction_id),
                aref['path'],
            )
            try:
                sz = os.path.getsize(file_path)  # 2for1
            except OSError as err:
                log.error(
                    'Sighting.post OSError %r assetReferences data: %r' % (err, aref)
                )
                _cleanup_post_and_abort(
                    result_data['id'], None, 'File not found: ' + str(aref)
                )
            if sz < 1:
                log.error(
                    'Sighting.post zero-size file for assetReferences data: %r' % (aref)
                )
                _cleanup_post_and_abort(
                    result_data['id'], None, 'File empty: ' + str(aref)
                )

        # files seem to exist in uploads dir, so lets move on
        from app.modules.submissions.models import Submission

        pub = False
        owner_guid = None
        if current_user is not None and not current_user.is_anonymous:
            owner_guid = current_user.guid
            pub = True
        submission, assets_added = Submission.create_submission_from_tus(
            'Sighting.post ' + result_data['id'],
            current_user,
            transaction_id,
        )

        sighting = Sighting(
            guid=result_data['id'],
            version=result_data.get('version', 2),
        )

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
                    enc_assets = _enc_assets(
                        assets_added, paths_wanted[i]
                    )  # exception if we dont have all we need
                    if enc_assets is not None:
                        encounter.add_assets_no_context(enc_assets)
                    log.debug('%r is adding enc_assets=%r' % (encounter, enc_assets))
                    sighting.add_encounter(encounter)
                    i += 1
                except Exception:
                    _cleanup_post_and_abort(
                        result_data['id'], submission, 'Problem with encounter/assets'
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
