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

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('sightings', description='Sightings')  # pylint: disable=invalid-name


def _cleanup_post_and_abort(guid, message='Unknown error'):
    # TODO actually clean up edm based on guid!!!
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
            _cleanup_post_and_abort(None, 'Missing encounters between data and result')
        if not len(data['encounters']) == len(result_data['encounters']):
            log.error(
                'Sighting.post imbalanced encounters in %r or %r' % (data, result_data)
            )
            _cleanup_post_and_abort(
                None, 'Imbalance in encounters between data and result'
            )

        # now we handle asset-related json that came in. note: arrays should be parallel in data/result_data
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
                        _cleanup_post_and_abort(None, 'Malformed assetReferences data')
                    key = ':'.join((aref['transactionId'], aref['path']))
                    if key in arefs_found:
                        arefs_found[key]['encs'].append(i)
                    else:
                        arefs_found[key] = aref.copy()
                        arefs_found[key]['encs'] = [i]
            i += 1

        # import utool as ut
        # ut.embed()
        # submission = Submission(major_type=filesystem, description='Sighting.post ' + result_data['id'])
        # owner_guid ? etc!

        rtn = {
            'success': True,
            'result': {
                # 'guid': str(encounter.guid),
                # 'version': encounter.version,
            },
        }
        return rtn

        # TODO genericize the code from encounter
        # will contain EncounterAssets objects to join to assets (dont load assets themselves)
        asset_refs = []
        if 'assets' in data and isinstance(data['assets'], list):
            from app.modules.encounters.models import EncounterAssets

            for asset_data in data['assets']:
                if isinstance(asset_data, dict) and 'guid' in asset_data:
                    # note: if an invalid asset guid is provided, foreign key contstraint error will be thrown when persisting
                    asset_ref = EncounterAssets(
                        encounter_guid=result_data['id'], asset_guid=asset_data['guid']
                    )
                    asset_refs.append(asset_ref)

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new houston Sighting'
        )
        try:
            with context:
                # TODO other houston-based relationships: orgs, projects, etc
                owner_guid = None
                pub = True  # legit? public if no owner?
                if current_user is not None and not current_user.is_anonymous:
                    owner_guid = current_user.guid
                    pub = False
                encounter = Sighting(  # Encounter(
                    guid=result_data['id'],
                    version=result_data.get('version', 2),
                    owner_guid=owner_guid,
                    public=pub,
                )
                encounter.assets = asset_refs
                db.session.add(encounter)
        except Exception as ex:
            log.error(
                'Encounter.post FAILED houston feather object creation guid=%r - will attempt to DELETE edm Encounter; (payload %r) ex=%r'
                % (
                    encounter.guid,
                    data,
                    ex,
                )
            )
            # clean up after ourselves by removing encounter from edm
            encounter.delete_from_edm(current_app)
            raise ex

        log.debug('Encounter.post created edm/houston guid=%r' % (encounter.guid,))
        rtn = {
            'success': True,
            'result': {
                'guid': str(encounter.guid),
                'version': encounter.version,
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
