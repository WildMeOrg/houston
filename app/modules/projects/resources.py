# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Projects resources
--------------------------
"""

import logging
from http import HTTPStatus

from flask import request
from flask_login import current_user  # NOQA

from app.extensions import db
from app.extensions.api import Namespace
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from flask_restx_patched import Resource

from . import parameters, schemas
from .models import Project

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('projects', description='Projects')  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['projects:read'])
class Projects(Resource):
    """
    Manipulations with Projects.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Project,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseProjectSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Project.
        """
        return Project.query_search(args=args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Project,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['projects:write'])
    @api.parameters(parameters.CreateProjectParameters())
    @api.response(schemas.DetailedProjectSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Project.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Project'
        )
        args['owner_guid'] = current_user.guid
        project = Project(**args)
        # User who creates the project gets added to it
        project.add_user(current_user)
        with context:
            db.session.add(project)

        db.session.refresh(project)

        return project


@api.route('/search')
@api.login_required(oauth_scopes=['projects:read'])
class ProjectElasticsearch(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Project,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseProjectSchema(many=True))
    @api.paginate()
    def get(self, args):
        search = {}
        args['total'] = True
        return Project.elasticsearch(search, **args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Project,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseProjectSchema(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()

        args['total'] = True
        return Project.elasticsearch(search, **args)


@api.route('/<uuid:project_guid>')
@api.login_required(oauth_scopes=['projects:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Project not found.',
)
@api.resolve_object_by_model(Project, 'project')
class ProjectByID(Resource):
    """
    Manipulations with a specific Project.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['project'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedProjectSchema())
    def get(self, project):
        """
        Get Project details by ID.
        """
        return project

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['project'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['projects:write'])
    @api.parameters(parameters.PatchProjectDetailsParameters())
    @api.response(schemas.DetailedProjectSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, project):
        """
        Patch Project details by ID.
        """

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Project details.'
        )
        with context:
            parameters.PatchProjectDetailsParameters.perform_patch(args, project)
            db.session.merge(project)
        return project

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['project'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['projects:delete'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, project):
        """
        Delete a Project by ID.
        """
        project.delete()
        return None
