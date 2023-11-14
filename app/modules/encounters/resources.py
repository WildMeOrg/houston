# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Encounters resources
--------------------------
"""

import logging
from http import HTTPStatus

from flask import make_response, request
from flask_login import current_user  # NOQA

import app.extensions.logging as AuditLog
from app.extensions import db
from app.extensions.api import Namespace, abort
from app.modules.sightings import schemas as sighting_schemas
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException
from flask_restx_patched import Resource

from . import parameters, schemas
from .models import Encounter

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('encounters', description='Encounters')  # pylint: disable=invalid-name


@api.route('/')
class Encounters(Resource):
    """
    Manipulations with Encounters.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Encounter,
            'action': AccessOperation.READ,
        },
    )
    @api.login_required(oauth_scopes=['encounters:read'])
    @api.response(schemas.BaseEncounterSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Encounter.
        """
        return Encounter.query_search(args=args)


@api.route('/search')
@api.login_required(oauth_scopes=['encounters:read'])
class EncounterElasticsearch(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Encounter,
            'action': AccessOperation.READ,
        },
    )
    @api.response(Encounter.get_elasticsearch_schema()(many=True))
    @api.paginate()
    def get(self, args):
        search = {}
        args['total'] = True
        return Encounter.elasticsearch(search, **args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Encounter,
            'action': AccessOperation.READ,
        },
    )
    @api.response(Encounter.get_elasticsearch_schema()(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()

        args['total'] = True
        return Encounter.elasticsearch(search, **args)


@api.route('/<uuid:encounter_guid>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Encounter not found.',
)
@api.resolve_object_by_model(Encounter, 'encounter')
class EncounterByID(Resource):
    """
    Manipulations with a specific Encounter.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['encounter'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedEncounterSchema())
    def get(self, encounter):
        """
        Get Encounter full details by ID.
        """

        return encounter

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['encounter'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['encounters:write'])
    @api.parameters(parameters.PatchEncounterDetailsParameters())
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(schemas.DetailedEncounterSchema())
    def patch(self, args, encounter):
        """
        Patch Encounter details by ID.
        """
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        context = api.commit_or_abort(
            db.session,
            default_error_message='Failed to update Encounter details.',
        )

        with context:
            try:
                parameters.PatchEncounterDetailsParameters.perform_patch(args, encounter)
            except HoustonException as ex:
                # Only 409 and 422 are valid for patch (so Jon says)
                status_code = ex.status_code if ex.status_code == 422 else 409
                abort(status_code, ex.message)
            db.session.merge(encounter)

        AuditLog.patch_object(log, encounter, args, duration=timer.elapsed())

        return encounter

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['encounter'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['encounters:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, encounter):
        """
        Delete an Encounter by ID.
        """
        # headers are strings, so we need to make into bools
        delete_individual = (
            request.headers.get('x-allow-delete-cascade-individual', 'false').lower()
            == 'true'
        )
        delete_sighting = (
            request.headers.get('x-allow-delete-cascade-sighting', 'false').lower()
            == 'true'
        )
        success, response = encounter.delete_frontend_request(
            delete_individual, delete_sighting
        )
        if not success:
            if 'vulnerableIndividual' in response or 'vulnerableSighting' in response:
                abort(
                    400,
                    'Delete failed because it would cause a delete cascade',
                    vulnerableIndividualGuid=response.get('vulnerableIndividual'),
                    vulnerableSightingGuid=response.get('vulnerableSighting'),
                )
            else:
                abort(400, 'Delete failed')
        else:
            # we have to roll our own response here (to return) as it seems the only way we can add a header
            #   (which we are using to denote the encounter DELETE also triggered a sighting DELETE, since
            #   no body is returned on a 204 for DELETE
            resp = make_response()
            resp.status_code = 204
            sighting_id = response.get('deletedSighting')
            if sighting_id:
                resp.headers['x-deletedSighting-guid'] = sighting_id
            individual_id = response.get('deletedIndividual')
            if individual_id:
                resp.headers['x-deletedIndividual-guids'] = individual_id

            return resp


@api.route('/debug/<uuid:encounter_guid>', doc=False)
@api.login_required(oauth_scopes=['encounters:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Encounter not found.',
)
@api.resolve_object_by_model(Encounter, 'encounter')
class EncounterDebugByID(Resource):
    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['encounter'],
            'action': AccessOperation.READ_DEBUG,
        },
    )
    @api.response(sighting_schemas.DebugSightingSchema())
    def get(self, encounter):
        return encounter.sighting


@api.route('/export')
@api.login_required(oauth_scopes=['export:write'])
class EncounterExport(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Encounter,
            'action': AccessOperation.EXPORT,
        },
    )
    def post(self):
        search = request.get_json()
        encs = Encounter.elasticsearch(search)
        if not encs:
            abort(400, 'No results to export')
        from flask import send_file

        from app.extensions.export.models import Export

        export = Export()
        for enc in encs:
            export.add(enc)
            export.add(enc.sighting)
            if enc.individual_guid:
                export.add(enc.individual)
        export.save()
        return send_file(
            export.filepath,
            mimetype='application/vnd.ms-excel',
            as_attachment=True,
            attachment_filename=export.filename,
        )
