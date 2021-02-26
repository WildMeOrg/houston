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


def _cleanup_post_and_abort(sighting_guid, submission_guid, message='Unknown error'):
    # TODO actually clean up edm based on guid!!!
    # TODO cleanup submission & assets (i guess???)
    abort(success=False, passed_message=message, message='Error', code=400)


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
    # @api.login_required(oauth_scopes=['sightings:write'])
    @api.parameters(parameters.CreateSightingParameters())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Sighting.
        """

        data = {}
        try:
            data_ = json.loads(request.data)
            data.update(data_)
        except Exception:
            pass

        response = current_app.edm.request_passthrough(
            'sighting.data', 'post', {'data': data}, ''
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
        if ('encounters' in data and 'encounters' not in result_data) or (
            'encounters' not in data and 'encounters' in result_data
        ):
            log.error(
                'Sighting.post missing encounters in one of %r or %r'
                % (data, result_data)
            )
            _cleanup_post_and_abort(
                None, None, 'Missing encounters between data and result'
            )
        if not len(data['encounters']) == len(result_data['encounters']):
            log.error(
                'Sighting.post imbalanced encounters in %r or %r' % (data, result_data)
            )
            _cleanup_post_and_abort(
                None, None, 'Imbalance in encounters between data and result'
            )
        # i think this was official declared as law today 2021-02-24
        if len(data['encounters']) < 1:
            log.error('Sighting.post empty encounters in %r / %r' % (data, result_data))
            _cleanup_post_and_abort(None, None, 'Must have at least one encounter')

        # now we handle asset-related json that came in. note: arrays should be parallel in data/result_data
        # this makes sure assetReferences is well-formed and also maps (future) assets to encounters

        # NOTE for simplicity i am going to assume assetReferences *share a common transaction id*  !!
        #  this will very likely always be true, but in the event it proves not to be, this will have to be altered
        #  to do multiple submission.import_tus_files() calls below

        arefs_found = {}
        i = 0
        while i < len(data['encounters']):
            enc_data = data['encounters'][i]
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
                            None, None, 'Malformed assetReferences data'
                        )
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
                _cleanup_post_and_abort(None, None, 'File not found: ' + str(aref))
            if sz < 1:
                log.error(
                    'Sighting.post zero-size file for assetReferences data: %r' % (aref)
                )
                _cleanup_post_and_abort(None, None, 'File empty: ' + str(aref))

        # files seem to exist in uploads dir, so lets move on
        from app.modules.submissions.models import Submission, SubmissionMajorType

        submission = Submission(
            major_type=SubmissionMajorType.filesystem,
            description='Sighting.post ' + result_data['id'],
        )
        pub = False
        owner_guid = None
        if current_user is not None and not current_user.is_anonymous:
            owner_guid = current_user.guid
            pub = True
        submission.owner_guid = owner_guid
        db.session.add(submission)
        log.info('created submission %r' % (submission))
        paths = submission.import_tus_files(transaction_id=transaction_id)
        log.info('submission imported %r' % (paths))

        # FIXME - we need to reduce submission.assets to only the ones represented by 'paths' here!!

        for asset in submission.assets:
            key = ':'.join((transaction_id, asset.path))
            if (
                key not in arefs_found
            ):  # this gets around assets we dont care about, see above
                continue
            log.debug('>>>>> %r => %r' % (key, arefs_found[key]))
            arefs_found[key]['asset'] = asset

        sighting = Sighting(
            guid=result_data['id'],
            version=result_data.get('version', 2),
        )

        from app.modules.encounters.models import Encounter, EncounterAssets

        if isinstance(result_data['encounters'], list):
            i = 0
            while i < len(result_data['encounters']):
                encounter = Encounter(
                    guid=result_data['encounters'][i]['id'],
                    version=result_data['encounters'][i].get('version', 2),
                    owner_guid=owner_guid,
                    public=pub,
                )
                asset_refs = []
                for key in arefs_found:
                    if (
                        i not in arefs_found[key]['encs']
                        or 'asset' not in arefs_found[key]
                    ):
                        continue
                    asset_refs.append(
                        EncounterAssets(
                            encounter_guid=encounter.guid,
                            asset_guid=arefs_found[key]['asset'].guid,
                        )
                    )
                log.debug('enc=%r asset_refs=%r' % (encounter, asset_refs))
                encounter.assets = asset_refs
                sighting.add_encounter(encounter)
                i += 1

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new houston Sighting'
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
